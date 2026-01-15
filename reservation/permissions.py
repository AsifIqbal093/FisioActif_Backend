from rest_framework import permissions

class IsAdminOrProfessional(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
            
        # Check for admin role or professional/teacher role
        return user.role == 'admin' or user.role in ['professional', 'teacher']
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        # Admin can access all, professionals only their own reservations
        return user.role == 'admin' or (user.role in ['professional', 'teacher'] and obj.professional == user)
    

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
            
        return user.role == 'admin'
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        return user.role == 'admin'
