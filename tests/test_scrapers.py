"""Site adapters: URL acquisition, product parsing, and the silent-block guard."""

from __future__ import annotations

import pytest

from scrapers.sites.base import ScrapedProduct, diagnose_empty
from scrapers.sites.generic import (
    ADAPTERS, Cults3DAdapter, MyMiniFactoryAdapter, get_adapter,
)


# ===========================================================================
# Product validation -- the silent-block guard
# ===========================================================================

def test_a_complete_product_is_valid():
    assert ScrapedProduct(title="Golem", images=["a.jpg"]).is_valid()


def test_a_product_with_no_title_is_a_failure_not_a_row():
    """When Cloudflare starts serving the generic landing page, the response
    is a perfectly good 200 full of HTML with no product in it."""
    product = ScrapedProduct(title="", images=["a.jpg"])
    assert not product.is_valid() and product.failure_reason() == "no title"


def test_a_product_with_no_images_is_a_failure():
    product = ScrapedProduct(title="Golem")
    assert not product.is_valid() and product.failure_reason() == "no images"


def test_a_whitespace_title_does_not_count_as_a_title():
    assert not ScrapedProduct(title="   ", images=["a.jpg"]).is_valid()


# ===========================================================================
# URL acquisition
# ===========================================================================

MMF_LISTING = '''
<a href="https://www.myminifactory.com/object/3d-print-stone-golem-123456">A</a>
<a href="https://www.myminifactory.com/object/3d-print-frost-wyrm-789012">B</a>
<a href="https://www.myminifactory.com/object/3d-print-stone-golem-123456">dupe</a>
<a href="/users/somecreator">not a product</a>
'''


def test_product_urls_are_extracted_from_markup():
    urls = MyMiniFactoryAdapter().product_urls_from_html(MMF_LISTING)
    assert len(urls) == 2


def test_duplicate_urls_are_removed_and_order_kept():
    urls = MyMiniFactoryAdapter().product_urls_from_html(MMF_LISTING)
    assert urls[0].endswith("123456") and urls[1].endswith("789012")


def test_non_product_links_are_ignored():
    urls = MyMiniFactoryAdapter().product_urls_from_html(MMF_LISTING)
    assert not any("/users/" in url for url in urls)


def test_the_trailing_numeric_id_is_the_key():
    """The saved-HTML acquisition mode keys on exactly this."""
    adapter = MyMiniFactoryAdapter()
    assert adapter.product_id(
        "https://www.myminifactory.com/object/3d-print-stone-golem-123456") == "123456"


def test_an_id_is_empty_for_a_non_product_url():
    assert MyMiniFactoryAdapter().product_id("https://example.com/about") == ""


def test_both_acquisition_modes_share_one_definition_of_a_product():
    """Live scroll and saved HTML use the same pattern, so they cannot drift."""
    adapter = MyMiniFactoryAdapter()
    saved = adapter.product_urls_from_html(MMF_LISTING)
    live = adapter.product_urls_from_html(MMF_LISTING)
    assert saved == live


def test_zero_results_dumps_every_anchor_for_diagnosis():
    """The difference between a ten-minute fix and an hour of guessing."""
    text = diagnose_empty('<a href="/a">x</a><a href="/b">y</a>')
    assert "/a" in text and "/b" in text


def test_a_page_with_no_anchors_at_all_gets_a_different_diagnosis():
    text = diagnose_empty("<html><body>blocked</body></html>")
    assert "rendered after load" in text or "block page" in text


# ===========================================================================
# Product parsing
# ===========================================================================

MMF_PRODUCT = '''<html><head>
<meta property="og:title" content="Stone Golem &amp; Base" />
<meta property="og:description" content="A heavy hitter. STL included." />
<meta property="og:image" content="https://images.myminifactory.com/a.jpg" />
</head><body>
<img src="https://images.myminifactory.com/b.jpg">
<img src="https://images.myminifactory.com/avatar-of-creator.jpg">
</body></html>'''


def test_title_is_read_from_open_graph():
    product = MyMiniFactoryAdapter().parse_product(MMF_PRODUCT)
    assert product.title == "Stone Golem & Base"


def test_html_entities_are_decoded():
    assert "&amp;" not in MyMiniFactoryAdapter().parse_product(MMF_PRODUCT).title


def test_description_is_read():
    product = MyMiniFactoryAdapter().parse_product(MMF_PRODUCT)
    assert "heavy hitter" in product.description


def test_images_are_collected_in_order():
    product = MyMiniFactoryAdapter().parse_product(MMF_PRODUCT)
    assert product.images[0].endswith("a.jpg")
    assert any(url.endswith("b.jpg") for url in product.images)


def test_avatars_and_chrome_are_excluded_from_images():
    product = MyMiniFactoryAdapter().parse_product(MMF_PRODUCT)
    assert not any("avatar" in url for url in product.images)


def test_a_parsed_product_validates():
    assert MyMiniFactoryAdapter().parse_product(MMF_PRODUCT, "u").is_valid()


def test_a_block_page_parses_to_an_invalid_product():
    """The whole point of validation: this must not become a row."""
    blocked = "<html><body><h1></h1><p>Checking your browser</p></body></html>"
    assert not MyMiniFactoryAdapter().parse_product(blocked).is_valid()


def test_a_fallback_h1_is_used_when_open_graph_is_absent():
    html = "<html><h1>Stone Golem</h1>" \
           '<img src="https://images.myminifactory.com/a.jpg"></html>'
    assert MyMiniFactoryAdapter().parse_product(html).title == "Stone Golem"


def test_images_are_capped_at_ten():
    images = "".join('<img src="https://images.myminifactory.com/%d.jpg">' % i
                     for i in range(20))
    product = MyMiniFactoryAdapter().parse_product("<h1>T</h1>" + images)
    assert len(product.images) == 10


def test_the_cults_adapter_parses_its_own_markup():
    html = '<meta property="og:title" content="Frost Wyrm" />' \
           '<meta property="og:image" content="https://x.cults3d.com/a.jpg" />'
    product = Cults3DAdapter().parse_product(html)
    assert product.title == "Frost Wyrm" and product.images


def test_adapters_are_selectable_by_name():
    assert isinstance(get_adapter("myminifactory"), MyMiniFactoryAdapter)
    assert set(ADAPTERS) == {"myminifactory", "cults3d"}


def test_an_unknown_site_exits_with_the_available_names():
    with pytest.raises(SystemExit, match="cults3d"):
        get_adapter("nosuchsite")
