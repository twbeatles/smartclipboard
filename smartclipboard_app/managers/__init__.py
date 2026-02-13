__all__ = ["SecureVaultManager", "ExportImportManager"]


def __getattr__(name):
    if name == "SecureVaultManager":
        from .secure_vault import SecureVaultManager

        return SecureVaultManager
    if name == "ExportImportManager":
        from .export_import import ExportImportManager

        return ExportImportManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
