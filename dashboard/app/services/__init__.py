"""Cross-cutting application services that don't own their own persistence.

Unlike a domain package (`app.session`, `app.projects`, ...), a service in
this package reads data already owned by an existing domain and performs a
local, user-facing action with it -- no new SQLite store is introduced
here. See `app.services.launcher` for the first example.
"""
