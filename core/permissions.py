from functools import wraps
from django.shortcuts import redirect, render

def session_role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            role = request.session.get('user_role')
            if role is None:
                return redirect(f"/login/?next={request.path}")
            if role not in allowed_roles:
                return render(request, 'core/403.html', status=403)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
