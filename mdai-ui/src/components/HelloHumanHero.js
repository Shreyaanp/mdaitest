import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
const DEFAULT_LOGO_SRC = '/hero/logo.svg';
const DEFAULT_HELIX_SRC = '/hero/test.gif';
export default function HelloHumanHero({ logoSrc, helixSrc }) {
    return (_jsxs("main", { className: "hero", "data-hello-hero": true, children: [_jsx("div", { className: "hero__helix", "aria-hidden": "true", children: _jsx("img", { src: helixSrc ?? DEFAULT_HELIX_SRC, alt: "DNA helix animation" }) }), _jsxs("div", { className: "hero__content", children: [_jsx("img", { className: "hero__logo", src: logoSrc ?? DEFAULT_LOGO_SRC, alt: "Mercle logo" }), _jsxs("h1", { className: "hero__headline", children: [_jsx("span", { children: "hello" }), _jsx("span", { children: "human" })] })] })] }));
}
