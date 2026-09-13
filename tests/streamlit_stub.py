"""
A small, strict stand-in for the parts of Streamlit that PayLens uses.

Purpose
  * Drive app.py headlessly through the whole user journey in tests
    (callbacks-before-rerun, widget state, widget-state cleanup, etc.).
  * Render an approximate HTML page of any journey state so the UI can be
    screenshotted in a browser when real Streamlit isn't installed.

It is intentionally stricter than Streamlit in a few places so that bugs
surface in tests: duplicate widget keys, >1 level of column nesting,
modifying a widget's state after it was rendered, clicking a button that is
disabled or not on screen, and passing a default value to a widget whose
key is already in session state all raise or are recorded.

Usage
    stub = install()                # puts the stub in sys.modules["streamlit"]
    stub.run("app.py")              # first render
    stub.click("btn_analyse_customer"); stub.run("app.py")
    html = stub.to_html()
"""

from __future__ import annotations

import html as _html
import sys
import types
from pathlib import Path
from typing import Any, Callable, Optional


class StubError(AssertionError):
    pass


class SessionState(dict):
    def __init__(self, owner: "StubStreamlit"):
        super().__init__()
        object.__setattr__(self, "_owner", owner)

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as e:
            raise AttributeError(item) from e

    def __setattr__(self, key, value):
        self[key] = value

    def __setitem__(self, key, value):
        owner = object.__getattribute__(self, "_owner")
        if owner._in_script and key in owner._rendered_widgets:
            raise StubError(f"st.session_state.{key} cannot be modified after the widget with key "
                            f"'{key}' is instantiated.")
        super().__setitem__(key, value)


class Node:
    def __init__(self, kind: str, **attrs):
        self.kind = kind
        self.attrs = attrs
        self.children: list[Node] = []


class _Ctx:
    def __init__(self, stub: "StubStreamlit", node: Node, col_depth_inc: int = 0):
        self.stub, self.node, self.inc = stub, node, col_depth_inc

    def __enter__(self):
        self.stub._stack.append(self.node)
        self.stub._col_depth += self.inc
        return self

    def __exit__(self, *exc):
        self.stub._stack.pop()
        self.stub._col_depth -= self.inc
        return False


class StubStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = SessionState(self)
        self._pending: list[tuple] = []
        self._widget_specs: dict[str, dict] = {}   # from the last run
        self._specs_this_run: dict[str, dict] = {}
        self._rendered_widgets: set[str] = set()
        self._widget_keys_ever: set[str] = set()
        self._clicked: Optional[str] = None
        self._in_script = False
        self._col_depth = 0
        self._stack: list[Node] = []
        self.root = Node("root")
        self.page_config: Optional[dict] = None
        self._first_call_done = False
        self.toasts: list[str] = []
        self.warnings: list[str] = []
        self.scrolls: list[str] = []
        self.errors: list[str] = []
        self._code_cache: dict[str, Any] = {}
        # components namespace
        comps = types.ModuleType("streamlit.components")
        v1 = types.ModuleType("streamlit.components.v1")
        v1.html = self._components_html
        comps.v1 = v1
        self.components = comps
        self._modules = {"streamlit.components": comps, "streamlit.components.v1": v1}

    # ------------------------------------------------------------------ run
    def set(self, key: str, value) -> "StubStreamlit":
        self._pending.append(("set", key, value))
        return self

    def click(self, key: str) -> "StubStreamlit":
        self._pending.append(("click", key))
        return self

    def run(self, app_path: str) -> "StubStreamlit":
        self._clicked = None
        # 1) apply queued interactions + callbacks (Streamlit runs callbacks before the script)
        for action in self._pending:
            if action[0] == "set":
                _, key, value = action
                spec = self._widget_specs.get(key)
                if spec is None:
                    raise StubError(f"No widget with key '{key}' was on screen")
                if spec.get("disabled"):
                    raise StubError(f"Widget '{key}' is disabled")
                old = self.session_state.get(key)
                dict.__setitem__(self.session_state, key, value)
                if old != value and spec.get("on_change"):
                    spec["on_change"](*(spec.get("args") or ()))
            else:
                _, key = action
                spec = self._widget_specs.get(key)
                if spec is None or spec["kind"] != "button":
                    raise StubError(f"No button with key '{key}' was on screen")
                if spec.get("disabled"):
                    raise StubError(f"Button '{key}' is disabled")
                self._clicked = key
                if spec.get("on_click"):
                    spec["on_click"](*(spec.get("args") or ()))
        self._pending.clear()

        # 2) execute the script
        self.root = Node("root")
        self._stack = [self.root]
        self._col_depth = 0
        self._rendered_widgets = set()
        self._specs_this_run = {}
        self._first_call_done = False
        self.toasts, self.scrolls = [], []
        path = str(Path(app_path).resolve())
        code = self._code_cache.get(path)
        if code is None:
            code = compile(Path(path).read_text(), path, "exec")
            self._code_cache[path] = code
        self._in_script = True
        try:
            exec(code, {"__name__": "__main__", "__file__": path})
        finally:
            self._in_script = False

        # 3) widget state cleanup, like Streamlit: widgets not rendered lose their state
        for key in list(self._widget_keys_ever - self._rendered_widgets):
            self.session_state.pop(key, None)
            self._widget_keys_ever.discard(key)
        self._widget_specs = self._specs_this_run
        return self

    # --------------------------------------------------------------- helpers
    def _mark_call(self, name: str):
        if name != "set_page_config":
            self._first_call_done = True

    def _add(self, node: Node):
        self._stack[-1].children.append(node)

    def _register(self, kind: str, key: str, **spec):
        if key is None:
            key = f"__auto_{kind}_{len(self._specs_this_run)}"
        if key in self._rendered_widgets:
            raise StubError(f"DuplicateWidgetID: key '{key}'")
        self._rendered_widgets.add(key)
        self._widget_keys_ever.add(key)
        self._specs_this_run[key] = {"kind": kind, **spec}
        return key

    def _check_default(self, key, provided: bool):
        if provided and key in self.session_state:
            self.warnings.append(f"Widget '{key}' created with a default value but also set via Session State")

    # ------------------------------------------------------------- page/layout
    def set_page_config(self, page_title=None, page_icon=None, layout="centered",
                        initial_sidebar_state="auto", menu_items=None):
        if self._first_call_done:
            raise StubError("set_page_config must be the first Streamlit call")
        self.page_config = dict(page_title=page_title, page_icon=page_icon, layout=layout)

    def container(self, height=None, border=None, key=None, gap="small"):
        self._mark_call("container")
        node = Node("container", key=key)
        self._add(node)
        return _Ctx(self, node)

    def columns(self, spec, *, gap="small", vertical_alignment="top", border=False):
        self._mark_call("columns")
        if self._col_depth >= 2:
            raise StubError("Columns can only be placed inside other columns up to one level of nesting")
        weights = [1] * spec if isinstance(spec, int) else list(spec)
        row = Node("columns", gap=gap, align=vertical_alignment)
        self._add(row)
        cols = []
        for w in weights:
            col = Node("column", weight=w)
            row.children.append(col)
            cols.append(_Ctx(self, col, col_depth_inc=1))
        return cols

    def expander(self, label, expanded=False, icon=None):
        self._mark_call("expander")
        node = Node("expander", label=label)
        self._add(node)
        return _Ctx(self, node)

    # --------------------------------------------------------------- elements
    def markdown(self, body, unsafe_allow_html=False, help=None):
        self._mark_call("markdown")
        self._add(Node("markdown", body=str(body), html=unsafe_allow_html))

    def toast(self, body, icon=None):
        self._mark_call("toast")
        self.toasts.append(body)

    def _components_html(self, html, width=None, height=None, scrolling=False):
        self._mark_call("components.html")
        import re
        m = re.search(r'getElementById\("([^"]+)"\)', html)
        if m:
            self.scrolls.append(m.group(1))
        self._add(Node("iframe", height=height))

    # ---------------------------------------------------------------- widgets
    def text_input(self, label, value=None, max_chars=None, key=None, type="default", help=None,
                   autocomplete=None, on_change=None, args=None, kwargs=None, *, placeholder=None,
                   disabled=False, label_visibility="visible", icon=None, width="stretch"):
        self._mark_call("text_input")
        self._check_default(key, value is not None)
        key = self._register("text_input", key, on_change=on_change, args=args, disabled=disabled)
        if key not in self.session_state:
            dict.__setitem__(self.session_state, key, value or "")
        val = self.session_state[key]
        if not isinstance(val, str):
            raise StubError(f"text_input '{key}' holds non-string {val!r}")
        self._add(Node("text_input", label=label, value=val, placeholder=placeholder or "",
                       hidden_label=label_visibility == "collapsed", key=key))
        return val

    def button(self, label, key=None, help=None, on_click=None, args=None, kwargs=None, *,
               type="secondary", icon=None, disabled=False, use_container_width=None, width="content"):
        self._mark_call("button")
        if type not in ("primary", "secondary", "tertiary"):
            raise StubError(f"bad button type {type}")
        key = self._register("button", key, on_click=on_click, args=args, disabled=disabled, label=label)
        # buttons don't keep state between runs
        self._widget_keys_ever.discard(key)
        stretch = width == "stretch" or bool(use_container_width)
        self._add(Node("button", label=label, type=type, disabled=disabled, stretch=stretch, key=key))
        return self._clicked == key

    def slider(self, label, min_value=None, max_value=None, value=None, step=None, format=None,
               key=None, help=None, on_change=None, args=None, kwargs=None, *, disabled=False,
               label_visibility="visible", width="stretch"):
        self._mark_call("slider")
        self._check_default(key, value is not None)
        key = self._register("slider", key, on_change=on_change, args=args, disabled=disabled)
        if key not in self.session_state:
            dict.__setitem__(self.session_state, key, value if value is not None else min_value)
        val = self.session_state[key]
        if not isinstance(val, int) or not (min_value <= val <= max_value):
            raise StubError(f"slider '{key}' value {val!r} outside [{min_value}, {max_value}] or not int")
        self._add(Node("slider", label=label, value=val, min=min_value, max=max_value,
                       fmt=format or "%d", key=key))
        return val

    def segmented_control(self, label, options, *, selection_mode="single", default=None,
                          format_func=str, key=None, help=None, on_change=None, args=None,
                          kwargs=None, disabled=False, label_visibility="visible", width="content"):
        self._mark_call("segmented_control")
        self._check_default(key, default is not None)
        key = self._register("segmented_control", key, on_change=on_change, args=args, disabled=disabled)
        if key not in self.session_state:
            dict.__setitem__(self.session_state, key, default)
        val = self.session_state[key]
        if val is not None and val not in options:
            raise StubError(f"segmented_control '{key}' value {val!r} not in options")
        self._add(Node("segmented", label=label, options=[(o, format_func(o)) for o in options],
                       value=val, key=key))
        return val

    def radio(self, *a, **k):  # pragma: no cover - fallback path not used with this stub
        raise StubError("radio fallback should not be used when segmented_control exists")

    # ---------------------------------------------------------------- queries
    def iter_nodes(self, node: Optional[Node] = None):
        node = node or self.root
        for child in node.children:
            yield child
            yield from self.iter_nodes(child)

    def buttons(self) -> dict:
        return {n.attrs["key"]: n.attrs for n in self.iter_nodes() if n.kind == "button"}

    def text(self) -> str:
        """All markdown bodies concatenated (for content assertions)."""
        return "\n".join(n.attrs["body"] for n in self.iter_nodes() if n.kind == "markdown")

    def container_keys(self) -> set:
        return {n.attrs.get("key") for n in self.iter_nodes() if n.kind == "container" and n.attrs.get("key")}

    # ---------------------------------------------------------------- HTML
    def to_html(self, title: str = "PayLens preview") -> str:
        body = "".join(self._render(c) for c in self.root.children)
        return (f"<!doctype html><html><head><meta charset='utf-8'>"
                f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
                f"<title>{_html.escape(title)}</title><style>{BASE_CSS}</style></head><body>"
                f"<div class='stApp' data-testid='stApp'><div data-testid='stMain'>"
                f"<div class='block-container' data-testid='stMainBlockContainer'>"
                f"<div class='stVerticalBlock' data-testid='stVerticalBlock'>{body}</div>"
                f"</div></div></div></body></html>")

    def _wrap(self, inner: str) -> str:
        return f"<div class='stElementContainer element-container' data-testid='stElementContainer'>{inner}</div>"

    def _label(self, text, hidden=False):
        if hidden:
            return ""
        return (f"<label data-testid='stWidgetLabel'><div data-testid='stMarkdownContainer'>"
                f"<p>{_html.escape(str(text))}</p></div></label>")

    def _render(self, n: Node) -> str:
        k, a = n.kind, n.attrs
        kids = "".join(self._render(c) for c in n.children)
        if k == "markdown":
            return self._wrap(f"<div class='stMarkdown' data-testid='stMarkdown'>"
                              f"<div data-testid='stMarkdownContainer'>{a['body']}</div></div>")
        if k == "container":
            cls = f" st-key-{a['key']}" if a.get("key") else ""
            return f"<div class='stVerticalBlock{cls}' data-testid='stVerticalBlock'>{kids}</div>"
        if k == "columns":
            gap = {"small": "1rem", "medium": "2rem", "large": "4rem"}.get(a["gap"], "1rem")
            align = {"top": "flex-start", "center": "center", "bottom": "flex-end"}.get(a["align"], "flex-start")
            return (f"<div class='stHorizontalBlock' data-testid='stHorizontalBlock' "
                    f"style='gap:{gap};align-items:{align}'>{kids}</div>")
        if k == "column":
            return (f"<div class='stColumn' data-testid='stColumn' style='flex:{a['weight']} 1 0%'>"
                    f"<div class='stVerticalBlock' data-testid='stVerticalBlock'>{kids}</div></div>")
        if k == "expander":
            return self._wrap(f"<div data-testid='stExpander' class='stExpander'><details open><summary>"
                              f"<div data-testid='stMarkdownContainer'><p>{_html.escape(a['label'])}</p></div>"
                              f"</summary><div class='stub-exp-body'><div class='stVerticalBlock' "
                              f"data-testid='stVerticalBlock'>{kids}</div></div></details></div>")
        if k == "iframe":
            return self._wrap(f"<iframe height='{a['height']}' style='border:0;display:block;height:0'></iframe>")
        if k == "text_input":
            return self._wrap(
                f"<div class='stTextInput' data-testid='stTextInput'>{self._label(a['label'], a['hidden_label'])}"
                f"<div data-baseweb='input' class='stub-input'><div data-baseweb='base-input' class='stub-base'>"
                f"<input type='text' value='{_html.escape(a['value'], quote=True)}' "
                f"placeholder='{_html.escape(a['placeholder'], quote=True)}'></div></div></div>")
        if k == "button":
            style = " style='width:100%'" if a["stretch"] else ""
            dis = " disabled" if a["disabled"] else ""
            return self._wrap(
                f"<div class='stButton'><button kind='{a['type']}' data-testid='stBaseButton-{a['type']}' "
                f"class='stub-btn'{style}{dis}><div data-testid='stMarkdownContainer'>"
                f"<p>{_html.escape(a['label'])}</p></div></button></div>")
        if k == "slider":
            pct = (a["value"] - a["min"]) / max(a["max"] - a["min"], 1) * 100
            fmt = a["fmt"].replace("%%", "%")
            val = fmt.replace("%d", str(a["value"]))
            lo, hi = fmt.replace("%d", str(a["min"])), fmt.replace("%d", str(a["max"]))
            return self._wrap(
                f"<div class='stSlider' data-testid='stSlider'>{self._label(a['label'])}"
                f"<div class='stub-slider'><div class='stub-track'><div class='stub-fill' style='width:{pct}%'></div>"
                f"<div role='slider' class='stub-thumb' style='left:{pct}%'></div>"
                f"<div data-testid='stSliderThumbValue' class='stub-thumbval' style='left:{pct}%'>{val}</div></div>"
                f"<div class='stub-ticks'><div data-testid='stSliderTickBarMin'>{lo}</div>"
                f"<div data-testid='stSliderTickBarMax'>{hi}</div></div></div></div>")
        if k == "segmented":
            btns = "".join(
                f"<button class='stub-segbtn' data-testid='stBaseButton-segmented_control"
                f"{'Active' if o == a['value'] else ''}'><div data-testid='stMarkdownContainer'>"
                f"<p>{_html.escape(lab)}</p></div></button>" for o, lab in a["options"])
            return self._wrap(f"<div class='stButtonGroup' data-testid='stButtonGroup'>{self._label(a['label'])}"
                              f"<div class='stub-seg'>{btns}</div></div>")
        return kids


def install() -> StubStreamlit:
    """Swap the stub in for ``streamlit`` and return it.

    Call ``uninstall()`` afterwards -- always via ``addCleanup`` so it runs on
    failure too. Without that restore the stub leaks into the rest of the
    process, which is why these tests used to be skipped whenever real
    Streamlit was installed, leaving the journey they assert unexercised.
    """
    stub = StubStreamlit()
    names = ["streamlit", *stub._modules]
    _saved.append({n: sys.modules.get(n) for n in names})

    sys.modules["streamlit"] = stub
    for name, mod in stub._modules.items():
        sys.modules[name] = mod
    # compat caches signatures per process — clear so it inspects this stub
    try:
        from src.ui import compat
        _saved[-1]["__compat_st__"] = compat.st
        compat._params.cache_clear()
        compat.st = stub
    except Exception:
        pass
    return stub


_saved: list = []


def uninstall() -> None:
    """Undo the most recent ``install()``, restoring real Streamlit if present."""
    if _saved:
        saved = _saved.pop()
        saved.pop("__compat_st__", None)
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod

    # Re-point compat at whatever ``streamlit`` now resolves to rather than at a
    # value saved by install(). pytest can import this file twice (as
    # ``tests.streamlit_stub`` and as ``streamlit_stub``), giving two _saved
    # stacks whose install/uninstall pairs do not line up, which used to leave a
    # dead stub in compat.st and break the real-Streamlit test that ran next.
    try:
        from src.ui import compat
        compat._params.cache_clear()
        current = sys.modules.get("streamlit")
        if current is not None and not isinstance(current, StubStreamlit):
            compat.st = current
    except Exception:
        pass


# Approximation of Streamlit's own base styles (only used for previews).
BASE_CSS = """
*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; }
body { font-family: "Source Sans Pro", -apple-system, "Segoe UI", sans-serif; font-size: 16px; color: #000000; background: #F2F2F7; }
.stApp { min-height: 100vh; }
[data-testid="stMain"] { width: 100%; }
.block-container { width: 100%; margin: 0 auto; padding: 6rem 1rem 10rem; }
.stVerticalBlock { display: flex; flex-direction: column; gap: 1rem; width: 100%; min-width: 0; }
.stHorizontalBlock { display: flex; flex-wrap: wrap; width: 100%; }
.stColumn { min-width: 0; width: 0; }
@media (max-width: 640px) { .stColumn { flex: 1 1 100% !important; min-width: 100%; } }
[data-testid="stMarkdownContainer"] p { margin: 0; }
.stMarkdown { width: 100%; }
label[data-testid="stWidgetLabel"] { display: flex; min-height: 1.5rem; margin-bottom: .25rem; font-size: 14px; }
.stub-input { display: flex; align-items: center; min-height: 2.5rem; border: 1px solid transparent; border-radius: .5rem; background: #EEF3F6; }
.stub-base { flex: 1; display: flex; }
.stub-input input { width: 100%; border: 0; background: transparent; padding: 0 .75rem; font-size: 1rem; outline: none; height: 2.5rem; }
.stButton button, .stub-segbtn { display: inline-flex; align-items: center; justify-content: center; min-height: 2.5rem; padding: .25rem .75rem; border-radius: .5rem; font-size: 1rem; cursor: pointer; }
.stub-seg { display: flex; gap: 0; width: 100%; }
.stub-segbtn { flex: 1; border: 1px solid #ccc; background: #fff; }
.stub-slider { padding: 1.4rem .5rem 0; }
.stub-track { position: relative; height: 4px; background: #DCE5EA; border-radius: 4px; }
.stub-fill { position: absolute; left: 0; top: 0; bottom: 0; background: #006BDE; border-radius: 4px; }
.stub-thumb { position: absolute; top: 50%; width: 16px; height: 16px; border-radius: 50%; background: #006BDE; transform: translate(-50%, -50%); }
.stub-thumbval { position: absolute; bottom: 12px; transform: translateX(-50%); font-size: 14px; }
.stub-ticks { display: flex; justify-content: space-between; font-size: 13px; margin-top: 6px; }
.stExpander details { padding: .75rem 1rem; }
.stExpander summary { cursor: pointer; }
.stub-exp-body { padding-top: .75rem; }
"""
