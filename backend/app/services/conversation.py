"""Backend-owned, process-local conversation state for D6."""
from threading import RLock
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


class ConversationService:
    def __init__(self):
        # shortcut: state is process-local; move to shared storage before multi-worker deployment.
        self._states = {}
        self._lock = RLock()

    def start(self, config: ExperimentConfig) -> ConversationState:
        state = ConversationState(
            session_id=str(uuid4()), current_algorithm=config.algorithm, last_config=config,
        )
        with self._lock:
            self._states[state.session_id] = state
        return state.model_copy(deep=True)

    def get(self, session_id: str) -> ConversationState:
        with self._lock:
            state = self._states.get(session_id)
            if state is None:
                raise MissingConversation
            return state.model_copy(deep=True)

    def revise(self, session_id: str, changes: dict) -> ConversationState:
        if not changes or set(changes) - EDITABLE_FIELDS:
            raise InvalidRevision("Unknown or empty revision fields")
        with self._lock:
            state = self._states.get(session_id)
            if state is None or state.last_config is None:
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
            self._states[session_id] = state
            return state.model_copy(deep=True)

    def record_run(self, session_id: str, config: ExperimentConfig, run_id: str) -> None:
        with self._lock:
            state = self._states.get(session_id)
            if state is None:
                raise MissingConversation
            self._states[session_id] = state.model_copy(update={
                "current_algorithm": config.algorithm, "last_config": config,
                "last_run_id": run_id,
            }, deep=True)

    def accept_parse(self, session_id: str, config: ExperimentConfig) -> ConversationState:
        with self._lock:
            state = self._states.get(session_id)
            if state is None:
                raise MissingConversation
            self._states[session_id] = state.model_copy(update={
                "current_algorithm": config.algorithm, "last_config": config,
                "modified_fields": [],
            }, deep=True)
            return self._states[session_id].model_copy(deep=True)


conversations = ConversationService()
