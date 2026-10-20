from cloudinary.utils import cloudinary_url
from django.conf import settings
from django.core.files.storage import Storage, storages
from django.utils.deconstruct import deconstructible


@deconstructible
class PropertyImageStorage(Storage):
    def __init__(self):
        self.storage = storages["default"]

    def _open(self, name, mode="rb"):
        return self.storage.open(name, mode)

    def _save(self, name, content):
        return self.storage.save(name, content)

    def delete(self, name):
        return self.storage.delete(name)

    def exists(self, name):
        return self.storage.exists(name)

    def size(self, name):
        return self.storage.size(name)

    def path(self, name):
        return self.storage.path(name)

    def listdir(self, path):
        return self.storage.listdir(path)

    def url(self, name):
        if settings.STORAGES["default"]["BACKEND"] != "cloudinary_storage.storage.MediaCloudinaryStorage":
            return self.storage.url(name)
        return cloudinary_url(
            name,
            cloud_name=settings.CLOUDINARY_STORAGE["CLOUD_NAME"],
            secure=True,
            format="webp",
            transformation=[{"width": 1200, "height": 1200, "crop": "limit", "quality": "auto"}],
        )[0]
