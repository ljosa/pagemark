"""Screen preferences survive relaunch and tolerate older or invalid settings."""
import pytest

from pagemark_app.display_preferences import Appearance, DisplayPreferences, DraftFont, ViewMode


class MemoryDefaults:
    def __init__(self, **values):
        self.values = values

    def objectForKey_(self, key):
        return self.values.get(key)

    def boolForKey_(self, key):
        return bool(self.values.get(key))

    def setObject_forKey_(self, value, key):
        self.values[key] = value

    setInteger_forKey_ = setDouble_forKey_ = setObject_forKey_


@pytest.mark.parametrize("old_pages,expected", [(False, ViewMode.CONTINUOUS), (True, ViewMode.PAGES)])
def test_old_view_preference_migrates_without_overriding_new_choice(old_pages, expected):
    defaults = MemoryDefaults(PagesView=old_pages)
    preferences = DisplayPreferences(defaults)
    assert preferences.view_mode == expected
    assert preferences.appearance == Appearance.SYSTEM
    preferences.view_mode = ViewMode.DRAFT
    preferences.appearance = Appearance.DARK
    preferences.draft_font = DraftFont("Menlo-Regular")
    relaunched = DisplayPreferences(defaults)
    assert relaunched.view_mode == ViewMode.DRAFT
    assert relaunched.appearance == Appearance.DARK
    assert relaunched.draft_font == DraftFont("Menlo-Regular")


@pytest.mark.parametrize("size", [None, "nonsense", -1, 0, 1000, float("nan"), float("inf")])
def test_invalid_display_preferences_fall_back_to_usable_defaults(size):
    preferences = DisplayPreferences(MemoryDefaults(ViewMode="bad", Appearance="bad",
                                                     DraftFontName=[], DraftFontSize=size))
    assert preferences.view_mode == ViewMode.CONTINUOUS
    assert preferences.appearance == Appearance.SYSTEM
    assert preferences.draft_font == DraftFont()
    assert preferences.zoom_for(ViewMode.DRAFT) == 1.25


@pytest.mark.parametrize("size", [18, 48])
def test_old_font_size_migrates_to_draft_zoom_and_explicit_zoom_survives_relaunch(size):
    defaults = MemoryDefaults(DraftFontName="Menlo-Regular", DraftFontSize=size)
    preferences = DisplayPreferences(defaults)
    assert preferences.draft_font == DraftFont("Menlo-Regular")
    assert preferences.zoom_for(ViewMode.DRAFT) * DraftFont.size == size * 1.25
    assert preferences.zoom_for(ViewMode.CONTINUOUS) == 1.25
    preferences.set_zoom(ViewMode.DRAFT, 1)
    preferences.set_zoom(ViewMode.PAGES, 2)
    relaunched = DisplayPreferences(defaults)
    assert relaunched.zoom_for(ViewMode.DRAFT) == 1
    assert relaunched.zoom_for(ViewMode.PAGES) == 2
    assert relaunched.zoom_for(ViewMode.CONTINUOUS) == 2


@pytest.mark.parametrize("stored,expected", [(0, .5), (100, 5), (float("nan"), 1.25),
                                           (float("inf"), 1.25), ("bad", 1.25)])
def test_stored_zoom_is_bounded_and_invalid_values_are_safe(stored, expected):
    preferences = DisplayPreferences(MemoryDefaults(LayoutZoom=stored, DraftZoom=stored))
    assert preferences.zoom_for(ViewMode.CONTINUOUS) == expected
    assert preferences.zoom_for(ViewMode.DRAFT) == expected
