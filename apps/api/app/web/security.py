"""Authorization for the server-rendered UI (R1.4).

The JSON API guards every mutation with `require_permission`, which raises
`PermissionDeniedError` and comes back as a 403 JSON envelope. The web UI needs
the same check, but a human has to be able to read the result:

* **GET** — a 403 `error.html` page. This needs no code here: the guard raises
  `PermissionDeniedError`, an `AppError`, and `app.web.errors` already renders
  `error.html` at the exception's own status code for any non-API path.
* **POST** — a 303 back to the page the form was on, carrying an `err` flash.
  Rendering a 403 body in response to a form submit would strand the user on a
  URL that cannot be reloaded or bookmarked, so the Post/Redirect/Get contract
  the rest of the web layer follows applies to denials too. That branch lives in
  `app.web.errors.register_web_error_handlers`.

**Decision D-B: ApexOS has exactly one user, the founder.** Their actor carries
`*`, so this guard denies nothing in dev *or* prod today, and it is deliberately
paired with no roles/permissions UI (building one is explicitly out of scope, and
G17 treats finding yourself building it as a signal the session has drifted).

It is still worth the ~20 lines: the enforcement point has to exist at each
mutation *before* a second principal does, because retrofitting guards onto
thirty-odd routes later is where coverage gaps come from. Permission codes here
mirror the API's (`customer.create`, `task.complete`, …) so the two surfaces
cannot drift into disagreeing about what a capability is called.
"""
from __future__ import annotations

from fastapi import Depends

from app.core.errors import PermissionDeniedError
from app.core.security import Actor, get_current_actor

# HTTP methods that render a page rather than mutate. A denial on one of these
# renders error.html; a denial on anything else redirects with a flash.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def permission_phrase(permission: str) -> str:
    """Turn a `resource.action` code into something a sentence can hold.

    `sales_order.confirm` -> "confirm sales orders".
    """
    resource, _, action = permission.partition(".")
    noun = resource.replace("_", " ")
    verb = (action or "change").replace("_", " ")
    return f"{verb} {noun}s" if not noun.endswith("s") else f"{verb} {noun}"


def require_web_permission(permission: str):
    """Dependency factory enforcing a `resource.action` permission on a web route.

    The web mirror of `app.core.security.require_permission`; see the module
    docstring for how GET and POST denials are rendered differently.
    """

    def _dep(actor: Actor = Depends(get_current_actor)) -> Actor:
        if not actor.has(permission):
            raise PermissionDeniedError(
                f"You do not have permission to {permission_phrase(permission)}."
            )
        return actor

    return _dep
