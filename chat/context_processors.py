def sidebar_sessions(request):
    """The logged-in user's chat sessions for the sidebar, most recently used first."""
    if not request.user.is_authenticated:
        return {}
    return {'sidebar_sessions': request.user.chat_sessions.only('id', 'name', 'updated_at')}
