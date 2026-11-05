"""Pages used by the unit tests and by tools/pixel_proof.py.

Every page holds the marker MARKER once.

ATTACKS: a person cannot see the marker. Proven in real Chromium by tools/pixel_proof.py: changing
the marker's letters changes no visible pixel.

CONTROLS: a person can see the marker, though the page looks suspicious to a naive filter. Proven the
same way: changing the marker's letters does change pixels. Removing these is a false positive.

"subtle" attacks are painted, but too faintly to read; the proof allows a tiny pixel difference there.
"""
MARKER = "QZXMARKERQZX"
_M = MARKER


def page(body: str, head: str = "", doctype: bool = True) -> str:
    dt = "<!doctype html>" if doctype else ""
    return (f'{dt}<html><head><meta charset="utf-8"><title>Test</title>{head}</head>'
            f'<body><h1>Visible heading</h1><p>Visible article text.</p>{body}<p>Closing line.</p></body></html>')


def style(css: str) -> str:
    return f"<style>{css}</style>"


ATTACKS = {
    # Inline CSS, the common forms.
    "display_none": page(f'<div style="display:none">{_M}</div>'),
    "display_none_upper": page(f'<div style="DISPLAY : NONE">{_M}</div>'),
    "visibility_hidden": page(f'<div style="visibility:hidden">{_M}</div>'),
    "visibility_collapse": page(f'<span style="visibility:collapse">{_M}</span>'),
    "opacity_zero": page(f'<div style="opacity:0">{_M}</div>'),
    "opacity_percent": page(f'<div style="opacity:0%">{_M}</div>'),
    "opacity_dot": page(f'<div style="opacity:.0">{_M}</div>'),
    "font_size_zero": page(f'<p style="font-size:0">{_M}</p>'),
    "font_size_zero_em": page(f'<p style="font-size:0em">{_M}</p>'),
    "font_half_pixel": {"unreadable": True, "html": page(f'<p style="font-size:0.5px">{_M}</p>')},
    "font_shorthand_zero": page(f'<p style="font:0/0 a">{_M}</p>'),
    "white_on_white": page(f'<p style="color:#fff">{_M}</p>'),
    "white_named": page(f'<p style="color:white">{_M}</p>'),
    "white_rgb": page(f'<p style="color:rgb(255,255,255)">{_M}</p>'),
    "white_hsl": page(f'<p style="color:hsl(0 0% 100%)">{_M}</p>'),
    "white_oklch": page(f'<p style="color:oklch(100% 0 0)">{_M}</p>'),
    "white_font_tag": page(f'<font color="white">{_M}</font>'),
    "black_on_black": page(f'<div style="background:#000"><p style="color:#000">{_M}</p>x</div>'),
    "same_on_colored": page(f'<div style="background-color:#123456;color:#123456">{_M}</div>'),
    "transparent_text": page(f'<p style="color:transparent">{_M}</p>'),
    "alpha_zero_text": page(f'<p style="color:rgba(0,0,0,0)">{_M}</p>'),
    "hex8_alpha_zero": page(f'<p style="color:#00000000">{_M}</p>'),
    "text_fill_transparent": page(f'<p style="-webkit-text-fill-color:transparent">{_M}</p>'),
    "offscreen_left": page(f'<div style="position:absolute;left:-9999px">{_M}</div>'),
    "offscreen_top": page(f'<div style="position:absolute;top:-9999px">{_M}</div>'),
    "offscreen_fixed": page(f'<div style="position:fixed;left:-5000px">{_M}</div>'),
    "offscreen_em": page(f'<div style="position:absolute;left:-999em">{_M}</div>'),
    "offscreen_calc": page(f'<div style="position:absolute;left:calc(-5000px - 10px)">{_M}</div>'),
    "offscreen_inset": page(f'<div style="position:absolute;inset:0 auto auto -9999px">{_M}</div>'),
    "text_indent": page(f'<div style="text-indent:-9999px">{_M}</div>'),
    "margin_left": page(f'<div style="margin-left:-9999px">{_M}</div>'),
    "zero_height_overflow": page(f'<div style="height:0;overflow:hidden">{_M}</div>'),
    "zero_width_overflow": page(f'<div style="width:0;overflow:hidden">{_M}</div>'),
    "one_pixel_box": page(f'<div style="position:absolute;width:1px;height:1px;overflow:hidden">{_M}</div>'),
    "max_height_zero": page(f'<div style="max-height:0;overflow:hidden">{_M}</div>'),
    "clip_rect": page(f'<div style="position:absolute;clip:rect(0,0,0,0)">{_M}</div>'),
    "clip_rect_spaces": page(f'<div style="position:absolute;clip:rect(0 0 0 0)">{_M}</div>'),
    "clip_path_inset": page(f'<div style="clip-path:inset(100%)">{_M}</div>'),
    "clip_path_inset_50": page(f'<div style="clip-path:inset(50%)">{_M}</div>'),
    "clip_path_circle": page(f'<div style="clip-path:circle(0)">{_M}</div>'),
    "clip_path_polygon": page(f'<div style="clip-path:polygon(0 0,0 0,0 0)">{_M}</div>'),
    "scale_zero": page(f'<div style="transform:scale(0)">{_M}</div>'),
    "scale_x_zero": page(f'<div style="transform:scaleX(0)">{_M}</div>'),
    "scale_property": page(f'<div style="scale:0">{_M}</div>'),
    "translate_away": page(f'<div style="transform:translateX(-99999px)">{_M}</div>'),
    "translate_property": page(f'<div style="translate:-99999px">{_M}</div>'),
    "matrix_zero": page(f'<div style="transform:matrix(0,0,0,0,0,0)">{_M}</div>'),
    "rotate_edge_on": page(f'<div style="transform:rotateX(90deg)">{_M}</div>'),
    "filter_opacity": page(f'<div style="filter:opacity(0)">{_M}</div>'),
    "content_visibility": page(f'<div style="content-visibility:hidden">{_M}</div>'),
    # HTML itself.
    "hidden_attribute": page(f"<div hidden>{_M}</div>"),
    "hidden_until_found": page(f'<div hidden="until-found">{_M}</div>'),
    "html_comment": page(f"<!-- {_M} -->"),
    "template_tag": page(f"<template>{_M}</template>"),
    "noscript_tag": page(f"<noscript>{_M}</noscript>"),
    "closed_dialog": page(f"<dialog>{_M}</dialog>"),
    "popover_closed": page(f"<div popover>{_M}</div>"),
    "datalist_tag": page(f'<datalist id="d"><option>{_M}</option></datalist>'),
    "iframe_fallback": page(f"<iframe>{_M}</iframe>"),
    "object_fallback": page(f'<object data="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==">{_M}</object>'),
    "canvas_fallback": page(f"<canvas>{_M}</canvas>"),
    "audio_fallback": page(f"<audio>{_M}</audio>"),
    "video_fallback": page(f"<video>{_M}</video>"),
    "cdata_section": page(f"<![CDATA[ {_M} ]]>"),
    "style_tag_text": page(f"<style>/* {_M} */</style>"),
    "json_ld": page(f'<script type="application/ld+json">{{"description":"{_M}"}}</script>'),
    "svg_desc": page(f'<svg width="10" height="10"><desc>{_M}</desc></svg>'),
    "svg_title": page(f'<svg width="10" height="10"><title>{_M}</title></svg>'),
    "svg_metadata": page(f'<svg width="10" height="10"><metadata>{_M}</metadata></svg>'),
    "svg_defs": page(f'<svg width="10" height="10"><defs><text>{_M}</text></defs></svg>'),
    "svg_zero_size": page(f'<svg width="0" height="0"><text y="20">{_M}</text></svg>'),
    "svg_display_none": page(f'<svg width="300" height="40"><text y="20" display="none">{_M}</text></svg>'),
    "svg_fill_none": page(f'<svg width="300" height="40"><text y="20" fill="none">{_M}</text></svg>'),
    "svg_fill_white": page(f'<svg width="300" height="40"><text y="20" fill="#fff">{_M}</text></svg>'),
    "svg_opacity": page(f'<svg width="300" height="40"><text y="20" opacity="0">{_M}</text></svg>'),
    # Stylesheets: what a filter that only reads style="" misses.
    "sheet_class": page(f'<div class="x">{_M}</div>', style(".x{display:none}")),
    "sheet_id": page(f'<div id="x">{_M}</div>', style("#x{visibility:hidden}")),
    "sheet_tag": page(f"<aside>{_M}</aside>", style("aside{display:none}")),
    "sheet_attribute": page(f'<div data-x="1">{_M}</div>', style('[data-x="1"]{display:none}')),
    "sheet_attr_prefix": page(f'<div data-x="abc">{_M}</div>', style('[data-x^="a"]{opacity:0}')),
    "sheet_descendant": page(f'<section><div><b>{_M}</b></div></section>', style("section b{font-size:0}")),
    "sheet_child": page(f'<section><b>{_M}</b></section>', style("section>b{color:#fff}")),
    "sheet_sibling": page(f"<hr><b>{_M}</b>", style("hr+b{display:none}")),
    "sheet_general_sibling": page(f"<hr><i></i><b>{_M}</b>", style("hr~b{display:none}")),
    "sheet_nth_child": page(f"<div><i>a</i><b>{_M}</b></div>", style("div b:nth-child(2){display:none}")),
    "sheet_last_child": page(f"<div><i>a</i><b>{_M}</b></div>", style("div b:last-child{display:none}")),
    "sheet_not": page(f"<b>{_M}</b>", style("b:not(.visible){display:none}")),
    "sheet_is": page(f"<b>{_M}</b>", style(":is(b,i){display:none}")),
    "sheet_has": page(f"<div><u></u>{_M}</div>", style("div:has(u){display:none}")),
    "sheet_where": page(f"<b>{_M}</b>", style(":where(b){display:none}")),
    "sheet_important": page(f'<div class="x" style="display:block">{_M}</div>', style(".x{display:none!important}")),
    "sheet_specificity": page(f'<div id="a" class="b">{_M}</div>', style("#a{display:none}.b{display:block}")),
    "sheet_later_wins": page(f'<div class="b">{_M}</div>', style(".b{display:block}.b{display:none}")),
    "sheet_css_comment": page(f'<div class="x">{_M}</div>', style(".x{dis/**/play:block;display/* */:none}")),
    "sheet_escape_class": page(f'<div class="hide1">{_M}</div>', style(r".\68ide1{display:none}")),
    "sheet_escape_property": page(f'<div class="x">{_M}</div>', style(r".x{displ\61y:none}")),
    "sheet_variable": page(f'<div class="x">{_M}</div>', style(":root{--d:none}.x{display:var(--d)}")),
    "sheet_variable_color": page(f'<div class="x">{_M}</div>', style(":root{--c:#fff}.x{color:var(--c)}")),
    "sheet_variable_fallback": page(f'<div class="x">{_M}</div>', style(".x{opacity:var(--nope,0)}")),
    "sheet_media_screen": page(f'<div class="x">{_M}</div>', style("@media screen{.x{display:none}}")),
    "sheet_media_wide": page(f'<div class="x">{_M}</div>', style("@media (min-width:1px){.x{display:none}}")),
    "sheet_supports": page(f'<div class="x">{_M}</div>', style("@supports (display:grid){.x{display:none}}")),
    "sheet_layer": page(f'<div class="x">{_M}</div>', style("@layer a{.x{display:none}}")),
    "sheet_nested_rule": page(f'<div class="p"><b>{_M}</b></div>', style(".p{b{display:none}}")),
    "sheet_nested_ampersand": page(f'<div class="p w">{_M}</div>', style(".p{&.w{display:none}}")),
    "sheet_nested_media": page(f'<div class="lg:hidden">{_M}</div>', style(r".lg\:hidden{@media (width>=64rem){display:none}}")),
    "sheet_nested_in_layer": page(f'<div class="p">{_M}</div>', style("@layer u{.p{@media (min-width:1px){opacity:0}}}")),
    "sheet_after_quote_in_class": page(f'<div class="p">{_M}</div>', style(r""".content-\[\"\"\]{color:red}.p{display:none}""")),
    "sheet_quirks_class_case": page(f'<div class="x">{_M}</div>', style(".X{display:none}"), doctype=False),
    "sheet_style_in_body": page(f'<style>.x{{display:none}}</style><div class="x">{_M}</div>'),
    "sheet_background_var": page(f'<div class="w"><p>{_M}</p>x</div>', style(":root{--w:#fff}.w{background:var(--w);color:var(--w)}")),
    "invalid_then_valid": page(f'<div style="display:none;display:nonsense">{_M}</div>'),
    "last_valid_wins": page(f'<div style="display:block;display:none">{_M}</div>'),
    # Parsing tricks.
    "nested_same_tag": page(f'<div style="display:none"><div>inner</div>{_M}</div>'),
    "deep_nesting": page(f'<div style="display:none">{"<div>" * 40}{_M}{"</div>" * 40}</div>'),
    "unclosed_hidden": f'<!doctype html><html><body><p>Visible article text.</p><div hidden>{_M}',
    "self_closing_ignored": page(f"<div hidden/>{_M}</div>"),
    "stray_end_tag": page(f'<div hidden></span>{_M}</div>'),
    "end_tag_blocked_by_table": page(f'<div hidden><table><tr><td></div>{_M}</td></tr></table></div>'),
    "duplicate_attribute": page(f'<div style="display:none" style="display:block">{_M}</div>'),
    "entity_in_style": page(f'<div style="display&#58;none">{_M}</div>'),
    "unquoted_style": page(f"<div style=display:none>{_M}</div>"),
    "visibility_inherited": page(f'<div style="visibility:hidden"><p><span>{_M}</span></p></div>'),
    "opacity_inherited": page(f'<div style="opacity:0"><p style="opacity:1">{_M}</p></div>'),
    "font_size_em_inherited": page(f'<div style="font-size:0"><p style="font-size:1em">{_M}</p></div>'),
    "text_indent_kellum": page(f'<div style="width:200px;text-indent:100%;white-space:nowrap;overflow:hidden">{_M}</div>'),
    "left_percent_viewport": page(f'<div style="position:absolute;left:-100%">{_M}</div>'),
    "zoom_tiny": {"unreadable": True, "html": page(f'<div style="zoom:.001">{_M}</div>')},
    # Faint rather than absent.
    "near_white": {"subtle": True, "html": page(f'<p style="color:#fefefe">{_M}</p>')},
    "near_white_alpha": {"subtle": True, "html": page(f'<p style="color:rgba(0,0,0,.01)">{_M}</p>')},
    "low_opacity": {"subtle": True, "html": page(f'<div style="opacity:.01">{_M}</div>')},
}

CONTROLS = {
    "plain": page(f"<p>{_M}</p>"),
    "white_on_dark": page(f'<div style="background:#111;color:#fff"><p>{_M}</p></div>'),
    "white_on_dark_sheet": page(f'<div class="d">{_M}</div>', style(".d{background:#222;color:#eee}")),
    "gray_on_white": page(f'<p style="color:#999">{_M}</p>'),
    "gradient_text": page(f'<p style="background:linear-gradient(red,blue);-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent">{_M}</p>'),
    "white_on_gradient_bg": page(f'<div style="background:linear-gradient(#000,#222);color:#fff"><p>{_M}</p></div>'),
    "variable_set_where_declared": page(f'<div class="o">{_M}</div>', style(":root{--w:#000;--c:var(--w)}.o{--w:#fff;color:var(--c)}")),
    "text_over_dark_layer": page(f'<div style="position:relative;color:#fff"><div style="position:absolute;inset:0;background:#000"></div><div style="position:relative">{_M}</div></div>'),
    "text_over_painted_before": page(f'<div class="h">{_M}</div>', style('.h{position:relative;z-index:0;color:#fff}.h::before{content:"";position:absolute;inset:0;background:#000;z-index:-1}')),
    "text_over_picture": page(f'<div style="position:relative;color:#fff"><img alt="" style="position:absolute;inset:0;width:100%;height:100%;background:#000" src="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2210%22 height=%2210%22%3E%3Crect width=%2210%22 height=%2210%22/%3E%3C/svg%3E"><div style="position:relative">{_M}</div></div>'),
    "nested_hover_not_applied": page(f'<div class="p">{_M}</div>', style(".p{&:hover{display:none}}")),
    "nested_phones_only": page(f'<div class="md:hidden">{_M}</div>', style(r".md\:hidden{color:red;@media (width<40rem){display:none}}")),
    "keyframes_not_a_rule": page(f'<div class="p">{_M}</div>', style("@keyframes p{from{display:none}to{opacity:0}}")),
    "font_face_not_a_rule": page(f'<div class="p">{_M}</div>', style("@font-face{font-family:x;display:none}")),
    "background_inherit": page(f'<div style="background-color:inherit;color:#222">{_M}</div>'),
    "object_without_data": page(f"<object>{_M}</object>"),
    "tooltip_percent_near": page(f'<div style="position:relative;margin-left:300px;width:100px"><span style="position:absolute;left:-100%">{_M}</span></div>'),
    "display_overridden": page(f'<div class="x" style="display:block">{_M}</div>', style(".x{display:none}")),
    "important_beats_inline": page(f'<div class="x" style="display:none">{_M}</div>', style(".x{display:block!important}")),
    "specificity_shows": page(f'<div id="a" class="b">{_M}</div>', style(".b{display:none}#a{display:block}")),
    "later_shows": page(f'<div class="b">{_M}</div>', style(".b{display:none}.b{display:block}")),
    "hidden_attr_overridden": page(f'<div hidden style="display:block">{_M}</div>'),
    "visibility_child_override": page(f'<div style="visibility:hidden"><span style="visibility:visible">{_M}</span></div>'),
    "font_zero_parent_reset": page(f'<div style="font-size:0"><span style="font-size:16px">{_M}</span></div>'),
    "opacity_half": page(f'<div style="opacity:.5">{_M}</div>'),
    "small_left_shift": page(f'<div style="position:relative;left:20px">{_M}</div>'),
    "left_on_static": page(f'<div style="left:-9999px">{_M}</div>'),
    "negative_small": page(f'<div style="margin-left:40px;position:relative;left:-20px">{_M}</div>'),
    "overflow_with_height": page(f'<div style="height:100px;overflow:hidden">{_M}</div>'),
    "zero_width_no_overflow": page(f'<div style="width:0;white-space:nowrap">{_M}</div>'),
    "inline_width_ignored": page(f'<span style="width:0;overflow:hidden">{_M}</span>'),
    "hidden_on_phones_only": page(f'<div class="x">{_M}</div>', style("@media (max-width:600px){.x{display:none}}")),
    "hidden_when_printing": page(f'<div class="x">{_M}</div>', style("@media print{.x{display:none}}")),
    "hidden_style_tag_print": page(f'<div class="x">{_M}</div>', '<style media="print">.x{display:none}</style>'),
    "dark_mode_only": page(f'<div class="x">{_M}</div>', style("@media (prefers-color-scheme:dark){.x{display:none}}")),
    "hover_rule": page(f'<div class="x">{_M}</div>', style(".x:hover{display:none}")),
    "pseudo_element_rule": page(f'<div class="x">{_M}</div>', style(".x::before{display:none}")),
    "other_class": page(f'<div class="y">{_M}</div>', style(".x{display:none}")),
    "class_case_standards": page(f'<div class="x">{_M}</div>', style(".X{display:none}")),
    "not_selector_shows": page(f'<b class="v">{_M}</b>', style("b:not(.v){display:none}")),
    "wrong_nth": page(f"<div><b>{_M}</b><i>a</i></div>", style("div b:nth-child(2){display:none}")),
    "comment_around": page(f"<!-- a --><p>{_M}</p><!-- b -->"),
    "closed_details_summary": page(f"<details><summary>{_M}</summary>inner</details>"),
    "open_dialog": page(f"<dialog open>{_M}</dialog>"),
    "svg_visible_text": page(f'<svg width="300" height="40"><text y="20">{_M}</text></svg>'),
    "invalid_display_ignored": page(f'<div style="display:nonsense">{_M}</div>'),
    "aria_hidden_visible": page(f'<div aria-hidden="true">{_M}</div>'),
    "text_after_implied_close": page(f'<p hidden>a<div>{_M}</div>'),
    "text_after_real_close": page(f'<div hidden>a</div>{_M}'),
    "scale_half": page(f'<div style="transform:scale(.5)">{_M}</div>'),
    "drawer_percent_moved": page(f'<div style="transform:translateX(10%)">{_M}</div>'),
    "transparent_bg": page(f'<p style="background:transparent">{_M}</p>'),
    "colored_on_semi_bg": page(f'<div style="background:rgba(0,0,0,.8);color:#fff">{_M}</div>'),
    "input_is_not_hidden": page(f'<input type="text"><p>{_M}</p>'),
    "class_hide_sized": page(f'<div class="hidden md:block">{_M}</div>'),
    "class_bootstrap_shown": page(f'<div class="d-none d-md-block">{_M}</div>'),
}

# Invisible in Chromium, and seenonly misses them: telling these apart takes real layout or painting.
# They are here so the limits are measured, not guessed. A fix moves one up to ATTACKS.
KNOWN_GAPS = {
    "covered_by_opaque_box": page(f'<div style="position:relative;height:40px"><div style="position:absolute">{_M}</div><div style="position:absolute;inset:0;background:#fff"></div></div>'),
    "clipped_by_parent": page(f'<div style="position:relative;height:30px;overflow:hidden"><div style="position:absolute;top:200px">{_M}</div></div>'),
    "css_mask": page(f'<div style="mask-image:linear-gradient(transparent,transparent)">{_M}</div>'),
    "svg_fill_opacity": page(f'<svg width="300" height="40"><text y="20" fill-opacity="0">{_M}</text></svg>'),
    "custom_clip_path": page(f"""<div style="clip-path:path('M0 0')">{_M}</div>"""),
    "animation_ends_hidden": page(f'<div class="x">{_M}</div>', style("@keyframes k{to{opacity:0}}.x{animation:k 0s forwards}")),
}

# These hide or show only with an external framework stylesheet, so a real browser cannot prove them
# here: they are checked by the unit tests alone.
NO_PIXEL_PROOF = {"class_hide_sized", "class_bootstrap_shown"}


def html_of(item) -> str:
    return item["html"] if isinstance(item, dict) else item


def is_unreadable(item) -> bool:
    """Painted as a speck: pixels change, but there is nothing to read. The proof skips these."""
    return isinstance(item, dict) and bool(item.get("unreadable"))


def is_subtle(item) -> bool:
    return isinstance(item, dict) and bool(item.get("subtle"))
