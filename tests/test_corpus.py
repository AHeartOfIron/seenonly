import pytest

from corpus import ATTACKS, CONTROLS, KNOWN_GAPS, MARKER, html_of
from seenonly import clean


@pytest.mark.parametrize("name", sorted(ATTACKS))
def test_attack_is_removed(name):
    r = clean(html_of(ATTACKS[name]))
    assert MARKER not in r.text, r.text
    assert MARKER not in r.html
    assert "Visible article text." in r.text


@pytest.mark.parametrize("name", sorted(CONTROLS))
def test_visible_text_stays(name):
    r = clean(html_of(CONTROLS[name]))
    assert MARKER in r.text, [f.to_dict() for f in r.findings]
    assert MARKER in r.html
    assert "Visible article text." in r.text


@pytest.mark.parametrize("name", sorted(KNOWN_GAPS))
def test_known_gap_is_still_a_gap(name):
    """If this fails, seenonly got better: move the page up to ATTACKS and update the README."""
    assert MARKER in clean(KNOWN_GAPS[name]).text
