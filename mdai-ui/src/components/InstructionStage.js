import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export default function InstructionStage({ title, subtitle, className }) {
    return (_jsx("div", { className: "overlay overlay--center", children: _jsxs("div", { className: `overlay-card ${className ?? ''}`, children: [_jsx("h1", { children: title }), subtitle ? _jsx("p", { children: subtitle }) : null] }) }));
}
