import reflex as rx


class LoginState(rx.State):
    _logged_in: bool = False
    _user: str = ''

    @rx.event
    def login(self):
        self._logged_in = True
        # retrieve user from auth state
        self._user = "testuser"

    @rx.event
    def logout(self):
        self._logged_in = False
        self._user = ""

    @rx.var
    def logged_in(self) -> bool:
        return self._logged_in
