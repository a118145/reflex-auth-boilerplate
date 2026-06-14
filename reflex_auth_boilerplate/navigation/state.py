import reflex as rx

from . import routes
from .nav_config import NAV_ITEMS
# from ..states import AuthState


class NavState(rx.State):

    symbol_active: list[bool] = [True] + [False] * (len(NAV_ITEMS) - 1)
    # active_route: str = NAV_ITEMS[0]["sub_items"][0]["route"]

    @rx.event
    def set_active(self, index: int):
        # auth_state = await self.get_state(AuthState)
        self.symbol_active = [i == index for i in range(len(NAV_ITEMS))]
        # self.active_route = NAV_ITEMS[index]["sub_items"][0]["route"]
        
        # print("Auth required:", NAV_ITEMS[index].get("auth_required", False))
        # print("Logged in:", auth_state._logged_in)
        
        # return new route if all checks pass
        return rx.redirect(NAV_ITEMS[index]["route"])

    @rx.event
    def set_active_route(self, route: str):
        # self.active_route = route
        pass

    @rx.event
    def to_home(self):
        return self.set_active(0)

    @rx.event
    def to_settings(self):
        self.symbol_active = [False] * len(NAV_ITEMS)
        return rx.redirect(routes.USER_SETTINGS_ROUTE)

