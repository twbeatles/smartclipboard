"""Table and history presentation controller."""


class TableController:
    def __init__(self, window):
        self.window = window

    def load_data(self):
        return self.window.load_data()

    def get_display_items(self):
        return self.window._get_display_items()

    def populate_table(self, items, theme):
        return self.window._populate_table(items, theme)

    def on_selection_changed(self):
        return self.window.on_selection_changed()

    def copy_item(self):
        return self.window.copy_item()

    def paste_selected(self):
        return self.window.paste_selected()

    def delete_selected(self):
        return self.window.delete_selected()

    def delete_selected_items(self):
        return self.window.delete_selected_items()

    def toggle_pin(self):
        return self.window.toggle_pin()

    def toggle_bookmark(self):
        return self.window.toggle_bookmark()

    def edit_note(self):
        return self.window.edit_note()

    def create_collection(self):
        return self.window.create_collection()

    def move_to_collection(self, collection_id):
        return self.window.move_to_collection(collection_id)

    def edit_tag(self):
        return self.window.edit_tag()

    def show_context_menu(self, pos):
        return self.window.show_context_menu(pos)

    def handle_drop_event(self, event):
        return self.window._handle_drop_event(event)
