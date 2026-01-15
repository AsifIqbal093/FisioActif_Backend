from django.conf import settings
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)

class UserManager(BaseUserManager):
    """Manager for users."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and return a user with an email and password."""
        if not email:
            raise ValueError('User must have an email!')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        user.is_active = False
        return user


    def create_superuser(self, email, password):
        """Create, save and return a super user."""
        if not email:
            raise ValueError('User must have an email!')
        user = self.create_user(email, password)
        user.is_superuser = True
        user.role = "admin"
        user.is_active = True
        user.save(using=self._db)
        return user



class User(AbstractBaseUser, PermissionsMixin):
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('professional', 'Professional'),
        ('collaborator', 'Collaborator'),
    )
    # existing fields
    email = models.EmailField(max_length=255, unique=True)
    bio = models.TextField(blank=True, null=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    full_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='professional'
    )

    photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)

    street = models.CharField(max_length=200, null=True, blank=True)
    city = models.CharField(max_length=200, null=True, blank=True)
    country = models.CharField(max_length=200, null=True, blank=True)
    state = models.CharField(max_length=200, null=True, blank=True)
    zipcode = models.CharField(max_length=100, null=True, blank=True)

    # ===== Added fields from JSON =====

    collaborator_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="External or display ID for collaborator"
    )
    specialty = models.CharField(max_length=255, blank=True, null=True)

    gender_senhora = models.BooleanField(default=False)
    gender_homem = models.BooleanField(default=False)

    domicilio = models.BooleanField(default=False)

    commission_executing_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00
    )
    commission_executing_euro = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )

    commission_responsible_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00
    )
    commission_responsible_euro = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )

    personal_mobile = models.CharField(max_length=20, blank=True, null=True)
    show_mobile_in_app = models.BooleanField(default=False)

    zappy_page = models.URLField(blank=True, null=True)

    # ===== Weekly availability =====

    monday_enabled = models.BooleanField(default=False)
    monday_start = models.TimeField(blank=True, null=True)
    monday_break_from = models.TimeField(blank=True, null=True)
    monday_break_to = models.TimeField(blank=True, null=True)
    monday_end = models.TimeField(blank=True, null=True)

    tuesday_enabled = models.BooleanField(default=False)
    tuesday_start = models.TimeField(blank=True, null=True)
    tuesday_break_from = models.TimeField(blank=True, null=True)
    tuesday_break_to = models.TimeField(blank=True, null=True)
    tuesday_end = models.TimeField(blank=True, null=True)

    wednesday_enabled = models.BooleanField(default=False)
    wednesday_start = models.TimeField(blank=True, null=True)
    wednesday_break_from = models.TimeField(blank=True, null=True)
    wednesday_break_to = models.TimeField(blank=True, null=True)
    wednesday_end = models.TimeField(blank=True, null=True)

    thursday_enabled = models.BooleanField(default=False)
    thursday_start = models.TimeField(blank=True, null=True)
    thursday_break_from = models.TimeField(blank=True, null=True)
    thursday_break_to = models.TimeField(blank=True, null=True)
    thursday_end = models.TimeField(blank=True, null=True)

    friday_enabled = models.BooleanField(default=False)
    friday_start = models.TimeField(blank=True, null=True)
    friday_break_from = models.TimeField(blank=True, null=True)
    friday_break_to = models.TimeField(blank=True, null=True)
    friday_end = models.TimeField(blank=True, null=True)

    saturday_enabled = models.BooleanField(default=False)
    saturday_start = models.TimeField(blank=True, null=True)
    saturday_break_from = models.TimeField(blank=True, null=True)
    saturday_break_to = models.TimeField(blank=True, null=True)
    saturday_end = models.TimeField(blank=True, null=True)

    sunday_enabled = models.BooleanField(default=False)
    sunday_start = models.TimeField(blank=True, null=True)
    sunday_break_from = models.TimeField(blank=True, null=True)
    sunday_break_to = models.TimeField(blank=True, null=True)
    sunday_end = models.TimeField(blank=True, null=True)

    objects = UserManager()
    USERNAME_FIELD = 'email'

    # Subscription fields
    # subscribed_pack = models.ForeignKey(
    #     'subscriptions.Pack',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='subscribers',
    #     help_text="Currently subscribed pack"
    # )
    # remaining_hours = models.DecimalField(
    #     max_digits=10,
    #     decimal_places=2,
    #     default=0,
    #     help_text="Remaining hours from subscription"
    # )
    # subscription_date = models.DateTimeField(
    #     null=True,
    #     blank=True,
    #     help_text="Date when user last subscribed"
    # )


class Customer(models.Model):
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    professionals = models.ManyToManyField(
        User,
        limit_choices_to={'role': 'professional'},
        related_name='clients',
        blank=True,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


# Backwards-compatibility: older code imported `Client` from `user.models`.
# Provide a proxy model so imports keep working and no DB migration is required.
class Client(Customer):
    class Meta:
        proxy = True
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'

    def __str__(self):
        # Keep the representation consistent with Customer
        return super().__str__()

