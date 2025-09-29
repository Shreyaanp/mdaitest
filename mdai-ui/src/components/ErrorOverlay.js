import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export default function ErrorOverlay({ message }) {
    return (_jsx("div", { className: "overlay error", children: _jsxs("div", { className: "overlay-card", children: [_jsx("h1", { children: "Something went wrong" }), _jsx("p", { children: message })] }) }));
}
