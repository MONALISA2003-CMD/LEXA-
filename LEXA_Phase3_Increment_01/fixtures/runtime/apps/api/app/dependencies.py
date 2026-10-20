def require_permission(_permission_code):
    def dependency():
        return None
    return dependency
