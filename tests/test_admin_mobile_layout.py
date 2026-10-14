import pytest

from roborock_local_server.management_app import _admin_only_wizard_html, _setup_wizard_html, _status_html
from roborock_local_server.standalone_admin import _admin_dashboard_html, _admin_login_html
from roborock_local_server.web_theme import STYLE_CSS

VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'

PAGES = {
    "login": _admin_login_html,
    "dashboard": lambda: _admin_dashboard_html({"title": "", "text": "", "links": []}),
    "status": _status_html,
    "setup wizard": _setup_wizard_html,
    "admin-only wizard": _admin_only_wizard_html,
}


@pytest.mark.parametrize("name", PAGES)
def test_every_admin_page_asks_the_phone_for_its_real_width(name):
    # Without this a phone lays the page out about 980px wide and shrinks it, so the layout is tiny
    # and none of the narrow-screen rules in the stylesheet ever apply.
    assert VIEWPORT in PAGES[name]()


def test_the_viewport_tag_sits_in_the_head_beside_the_charset():
    html = _admin_dashboard_html({"title": "", "text": "", "links": []})

    assert html.index('<meta charset="utf-8">') < html.index(VIEWPORT) < html.index("</head>")


def test_the_stylesheet_reflows_the_header_and_facts_on_a_phone():
    phone_rules = STYLE_CSS.split("@media (max-width: 600px)")[-1]

    assert "nav .brand-logo" in phone_rules
    assert ".rls-facts" in phone_rules
    assert ".rls-spacer { display: none; }" in phone_rules
