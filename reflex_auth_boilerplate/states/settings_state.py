import reflex as rx
from sqlmodel import select
from .auth_state import AuthState
from ..models.models import UserModel


class SettingsState(AuthState):
    _user_token: str | None = None
    _num_owned_entities: int = 0
    _num_shared_entities: int = 0

    @rx.var
    def user_id(self) -> int | None:
        return self._user_id

    @rx.var
    def is_admin(self) -> bool:
        return self._user_acl > 0

    @rx.event
    async def retrieve_user_info(self):
        if self._user_id is None:
            return
        with rx.session() as session:
            user = session.exec(
                select(UserModel).where(UserModel.id == self._user_id)
            ).first()
            if not user:
                return
            self._user_token = user.api_token
            self._num_owned_entities = len(user.owned_entities)
            self._num_shared_entities = len(user.shared_entities)
        print(f"User info retrieved:")
        print(f"User ID: {self._user_id}")
        print(f"User mail: {self._user_mail}")
        print(f"User ACL: {self._user_acl}")
        print(f"User token: {self._user_token}")
        print(f"Num owned entities: {self._num_owned_entities}")
        print(f"Num shared entities: {self._num_shared_entities}")

    async def logout(self):
        self._user_token = None
        self._num_owned_entities = 0
        self._num_shared_entities = 0
        print(f"User logged out:")
        print(f"User token: {self._user_token}")
        print(f"Num owned entities: {self._num_owned_entities}")
        print(f"Num shared entities: {self._num_shared_entities}")
