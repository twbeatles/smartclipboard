__all__ = [
    "SettingsDialog",
    "SecureVaultDialog",
    "ClipboardActionsDialog",
    "ExportDialog",
    "ImportDialog",
    "TrashDialog",
    "HotkeySettingsDialog",
    "SnippetDialog",
    "SnippetManagerDialog",
    "TagEditDialog",
    "StatisticsDialog",
    "CopyRulesDialog",
]


def __getattr__(name):
    if name == "SettingsDialog":
        from .settings import SettingsDialog

        return SettingsDialog
    if name == "SecureVaultDialog":
        from .secure_vault import SecureVaultDialog

        return SecureVaultDialog
    if name == "ClipboardActionsDialog":
        from .clipboard_actions import ClipboardActionsDialog

        return ClipboardActionsDialog
    if name == "ExportDialog":
        from .export_dialog import ExportDialog

        return ExportDialog
    if name == "ImportDialog":
        from .import_dialog import ImportDialog

        return ImportDialog
    if name == "TrashDialog":
        from .trash_dialog import TrashDialog

        return TrashDialog
    if name == "HotkeySettingsDialog":
        from .hotkeys import HotkeySettingsDialog

        return HotkeySettingsDialog
    if name == "SnippetDialog":
        from .snippets import SnippetDialog

        return SnippetDialog
    if name == "SnippetManagerDialog":
        from .snippets import SnippetManagerDialog

        return SnippetManagerDialog
    if name == "TagEditDialog":
        from .tags import TagEditDialog

        return TagEditDialog
    if name == "StatisticsDialog":
        from .statistics import StatisticsDialog

        return StatisticsDialog
    if name == "CopyRulesDialog":
        from .copy_rules import CopyRulesDialog

        return CopyRulesDialog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
