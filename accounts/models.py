from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractUser):
    is_superuser = models.BooleanField(_("superuser status"), default=False)
    is_staff = models.BooleanField(_("staff status"), default=False)
    is_active = models.BooleanField(_("active"), default=True)
    groups = models.ManyToManyField(
        "auth.Group",
        verbose_name=_("groups"),
        blank=True,
        related_name="user_set",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        verbose_name=_("user permissions"),
        blank=True,
        related_name="user_set",
        related_query_name="user",
    )
    username = None
    email = models.EmailField(unique=True)
    phone = models.CharField(_("Phone"), max_length=32, blank=True)
    birth_date = models.DateField(_("Date of birth"), blank=True, null=True)
    country = models.CharField(_("Country"), max_length=2, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="user_email_case_insensitive_unique")]

    def __str__(self):
        return self.email
