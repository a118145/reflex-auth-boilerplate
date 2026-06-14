import reflex as rx
from sqlmodel import select
from ..navigation import NavState
from ..models.models import UserModel
from ..utils import validate_mail, validate_password, verify_password
from ..navigation.routes import HOME_ROUTE


class AuthState(rx.State):
    _logged_in: bool = False
    login_dialog_error: str = ""
    login_dialog_open: bool = False
    logout_dialog_open: bool = False
    register_dialog_open: bool = False
    _user_id: int | None = None
    _user_mail: str = ''
    _user_acl: int = 0
    dialog_error: str = ''

    @rx.event
    def login(self, form_data: dict):
        self.dialog_error = ""
        mail = form_data.get("mail", "")
        password = form_data.get("password", "")

        if not validate_mail(mail):
            self.dialog_error = "Invalid email address"
            return

        with rx.session() as session:
            user_obj = session.exec(
                select(UserModel).where(UserModel.email == mail)
            ).first()
            if not user_obj or not verify_password(password, user_obj.pw_hash):
                self.dialog_error = "Invalid email or password"
                return

        self._user_id = user_obj.id
        self._user_mail = user_obj.email
        self._user_acl = user_obj.access_lvl
        self._logged_in = True
        self.login_dialog_open = False
        rx.toast.success("Login successful")


    @rx.event
    def register(self, form_data: dict):
        self.dialog_error = ""
        mail = form_data.get("mail", "")
        password = form_data.get("password", "")
        confirm_password = form_data.get("confirm_password", "")

        if not validate_mail(mail):
            self.dialog_error = "Invalid email address"
            return

        error, pw_hash = validate_password(password, confirm_password)
        if error:
            self.dialog_error = error
            return

        with rx.session() as session:
            existing = session.exec(
                select(UserModel).where(UserModel.email == mail)
            ).first()
            if existing:
                self.dialog_error = "Email already registered"
                return

            user_obj = UserModel(email=mail, pw_hash=pw_hash)
            session.add(user_obj)
            session.commit()
            session.refresh(user_obj)

        self._user_id = user_obj.id
        self._user_mail = user_obj.email
        self._user_acl = user_obj.access_lvl
        self._logged_in = True
        self.register_dialog_open = False
        rx.toast.success("Registration successful")

    @rx.event
    async def logout(self):
        from ..states.settings_state import SettingsState
        settings = await self.get_state(SettingsState)
        await settings.logout()
        self._user_id = None
        self._user_mail = ''
        self._user_acl = 0
        self._logged_in = False
        print("Logged in:", self._logged_in)
        self.logout_dialog_open = False
        return [
            rx.redirect(HOME_ROUTE),
            rx.toast.success("Log out successful")
        ]

    @rx.var
    def is_logged_in(self) -> bool:
        return self._logged_in


    @rx.event
    def open_dialog(self, val: str):
        if val == "logout":
            self.logout_dialog_open = True
        elif val == "login":
            self.login_dialog_open = True
        elif val == "register":
            self.register_dialog_open = True

    @rx.event
    def close_dialog(self, val: str):
        if val == "logout":
            self.logout_dialog_open = False
        elif val == "login":
            self.login_dialog_open = False
        elif val == "register":
            self.register_dialog_open = False

    @rx.event
    def redir(self):
        return rx.redirect("/")

    

def require_login(page: rx.app.ComponentCallable) -> rx.app.ComponentCallable:
    """Decorator to require authentication before rendering a page.
    If the user is not authenticated, then redirect to the login page.
    Args:
        page: The page to wrap.
    Returns:
        The wrapped page component.
    """

    def protected_page():
        return rx.fragment(
            rx.cond(
                # AuthState.is_hydrated & AuthState._logged_in,  # type: ignore
                AuthState.is_logged_in,  # type: ignore
                page(),
                rx.center(
                    # When this text mounts, it will redirect to the login page
                    rx.text(
                        "Loading...", 
                        on_mount=NavState.to_home
                    ),
                ),
            )
        )
    protected_page.__name__ = page.__name__
    return protected_page