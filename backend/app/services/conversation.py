"""Backend-owned, process-local conversation state for D6."""
import os
from threading import RLock
from time import monotonic
from uuid import uuid4

from pydantic import ValidationError

from app.schemas.models import ConversationState, ExperimentConfig

EDITABLE_FIELDS = {
    "algorithm", "input.size", "input.distribution", "input.seed", "input.values",
    "visualization.enabled", "metrics",
}


class MissingConversation(Exception):
    pass


class InvalidRevision(Exception):
    pass


class RunConfigConflict(Exception):
    pass


class ExpiredConversation(MissingConversation):
    pass


class ConversationCapacity(Exception):
    pass


class ConversationService:
    def __init__(self, ttl_seconds=None, max_sessions=None, clock=monotonic):
        # shortcut: state is process-local; move to shared storage before multi-worker deployment.
        self._states = {}
        self._lock = RLock()
        self._clock = clock
        self._ttl = (ttl_seconds if ttl_seconds is not None else
                     int(os.getenv("ALGOVERSE_SESSION_TTL_SECONDS", "1800")))
        self._max = (max_sessions if max_sessions is not None else
                     int(os.getenv("ALGOVERSE_MAX_SESSIONS", "100")))
        if self._ttl <= 0 or self._max <= 0:
            raise ValueError("Session TTL and capacity must be positive")

    def _active(self, session_id):
        entry = self._states.get(session_id)
        if entry is None:
            raise MissingConversation
        state, touched = entry
        if self._clock() - touched >= self._ttl:
            del self._states[session_id]
            raise ExpiredConversation
        return state

    def _store(self, state):
        self._states[state.session_id] = (state.model_copy(deep=True), self._clock())

    def start(self, config: ExperimentConfig) -> ConversationState:
        state = ConversationState(
            session_id=str(uuid4()), current_algorithm=config.algorithm, last_config=config,
        )
        with self._lock:
            for key, (_, touched) in list(self._states.items()):
                if self._clock() - touched >= self._ttl:
                    del self._states[key]
            if len(self._states) >= self._max:
                raise ConversationCapacity
            self._store(state)
        return state.model_copy(deep=True)

    def get(self, session_id: str) -> ConversationState:
        with self._lock:
            return self._active(session_id).model_copy(deep=True)

    def revise(self, session_id: str, changes: dict) -> ConversationState:
        if not changes or set(changes) - EDITABLE_FIELDS:
            raise InvalidRevision("Unknown or empty revision fields")
        with self._lock:
            state = self._active(session_id)
            if state.last_config is None:
                raise MissingConversation
            data = state.last_config.model_dump()
            if ("input.size" in changes and data["input"]["values"] is not None
                    and not ("input.values" in changes and changes["input.values"] is None)):
                raise InvalidRevision("Clear input.values before changing input.size")
            for path, value in changes.items():
                target = data
                parts = path.split(".")
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = value
            try:
                config = ExperimentConfig.model_validate(data)
            except ValidationError as exc:
                raise InvalidRevision("Revised configuration is invalid") from exc
            state = state.model_copy(update={
                "current_algorithm": config.algorithm, "last_config": config,
                "modified_fields": list(changes),
            }, deep=True)
            self._store(state)
            return state.model_copy(deep=True)

    def assert_config(self, session_id: str, config: ExperimentConfig) -> None:
        with self._lock:
            state = self._active(session_id)
            if state.last_config != config:
                raise RunConfigConflict("Run config differs from confirmed conversation config")

    def execute_run(self, session_id: str, config: ExperimentConfig, execute):
        """Keep validation, execution, persistence and state update atomic to revisions."""
        with self._lock:
            self.assert_config(session_id, config)
            result = execute()
            state = self._active(session_id)
            self._store(state.model_copy(update={"last_run_id": result.run_id}, deep=True))
            return result

    def accept_parse(self, session_id: str, config: ExperimentConfig,
                     confirmed_changes: dict) -> ConversationState:
        if not confirmed_changes:
            raise MissingConversation
        if set(confirmed_changes) - EDITABLE_FIELDS:
            raise InvalidRevision("Unknown revision fields")
        with self._lock:
            self._active(session_id)
            candidate = config.model_dump()
            for path, value in confirmed_changes.items():
                target = candidate
                for part in path.split("."):
                    target = target[part]
                if target != value:
                    raise InvalidRevision("Provider disagrees with confirmed changes")
            return self.revise(session_id, confirmed_changes)


conversations = ConversationService()
