"""Cognitive kernel — the single pipeline every request goes through.

    perceive -> understand -> decide -> act -> remember -> react

* understand: the deterministic intent router turns clear commands into a
  concrete tool + arguments; everything else is left to the language model.
* decide: the shared safety policy lets harmless actions run and holds risky
  ones for confirmation — spoken/typed ("yes" / "no") or the UI Approve button.
* act: tools run through the same unified registry the brain uses.
* remember: every action is written to memory, so the assistant knows what it did.
* react: every action is published on the event bus, where triggers can react.

Chat, streaming chat, voice, automations and triggers all call the kernel, so
behaviour and safety are identical however you talk to Atulya.
"""
from __future__ import annotations

import logging
import re
import time
from collections import OrderedDict
from typing import Any, AsyncIterator

from atulya.agent.intent_router import route_intent
from atulya.cognition import safety
from atulya.cognition.planner import PLAN_TOOL, Plan, Planner, looks_failed, steps_for_clause, verify_step
from atulya.cognition.toolbelt import EXCLUDED_FROM_BRAIN
from atulya.llm import AtulyaLLM, LLMEvent, LLMResponse, _chunk_text, get_default_llm
from yantra.events import EventBus, default_bus

logger = logging.getLogger(__name__)

KERNEL_PROVIDER = "Atulya Kernel"
KERNEL_ORIGIN = "kernel"
# Commands the user authored in advance (scheduled jobs, trigger rules) were
# approved when they were created, so they don't stop to ask again.
PRE_AUTHORIZED_SOURCES = {"automation", "trigger"}
PENDING_TTL_SECONDS = 120
_MAX_PENDING = 256

_FILLER = {"please", "ji", "sir", "atulya", "it", "ahead", "for", "sure", "thanks", "thank", "you", "that", "now", "karo", "do"}
# No "ha": laughter ("ha ha") must never release a held action.
_AFFIRM = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "confirmed", "approve", "approved",
           "proceed", "haan", "go", "do"}
_DENY = {"no", "nope", "nah", "cancel", "stop", "dont", "abort", "nahi", "mat", "never", "mind", "nevermind"}


def confirmation_intent(text: str) -> str | None:
    """Return 'affirm' / 'deny' when the whole utterance is a clear yes / no.

    Deliberately strict: "stop the music" is a new command, not a cancel, and
    only a clear yes can release a held action.
    """
    tokens = re.sub(r"[^\w\s]", "", (text or "").lower()).split()
    if not tokens or len(tokens) > 6:
        return None
    if tokens[0] in _DENY and all(t in _DENY or t in _FILLER for t in tokens):
        return "deny"
    if tokens[0] in _AFFIRM and all(t in _AFFIRM or t in _FILLER for t in tokens):
        return "affirm"
    return None


def _brain_kwargs(
    history: list[dict[str, str]] | None,
    approved_tool: dict[str, Any] | None,
    provider: str,
    tools_enabled: bool,
) -> dict[str, Any]:
    """Only the arguments that carry information, so any brain with a narrower
    ``ask``/``stream`` signature (e.g. a test double) still works."""
    kwargs: dict[str, Any] = {}
    if history:
        kwargs["history"] = history
    if approved_tool:
        kwargs["approved_tool_call"] = approved_tool
    if provider:
        kwargs["provider"] = provider
    if not tools_enabled:
        kwargs["tools_enabled"] = False
    return kwargs


def _is_privileged(user: Any, source: str) -> bool:
    """May this caller perform confirmation-level actions at all?

    Web users carry a role: only admins may unlock doors, send email, delete
    data or run code — a guest account can still turn on lights or set
    reminders. Pre-authorized sources (automations, trigger rules) are created
    by admins. Callers without role information (CLI, direct use) are local
    and trusted.
    """
    if source in PRE_AUTHORIZED_SOURCES:
        return True
    if isinstance(user, dict):
        return user.get("role") == "admin"
    return True


def _kernel_tools() -> set[str]:
    from atulya.agent import tools as agent_tools

    return set(agent_tools.TOOL_REGISTRY) - EXCLUDED_FROM_BRAIN


# ── trace: the real stages a request went through, for UIs to display ──────
def _step(stage: str, title: str, detail: str) -> dict[str, str]:
    return {"stage": stage, "title": title, "detail": str(detail)[:240]}


def _describe_call(tool: str, args: dict[str, Any]) -> str:
    shown = ", ".join(f"{k}={v}" for k, v in args.items() if v not in ("", None))
    return f"{tool}({shown})"


def _brain_trace(response: Any, lead: list[dict[str, str]]) -> list[dict[str, str]]:
    steps = list(lead)
    for s in getattr(response, "tool_steps", None) or []:
        steps.append(_step("act", "Tool", f"{s.get('tool')}: {'done' if s.get('success') else 'failed'}"))
    if getattr(response, "needs_approval", False):
        pending = getattr(response, "pending_tool", None) or {}
        steps.append(_step("decide", "Needs confirmation",
                           safety.describe_action(pending.get("tool", ""), pending.get("arguments"))))
    else:
        steps.append(_step("think", "Answer", f"Answered by {getattr(response, 'provider', '') or 'the brain'}"))
    return steps


def _set_trace(response: Any, trace: list[dict[str, str]]) -> Any:
    try:
        response.trace = trace
    except (AttributeError, TypeError):  # a foreign response object
        pass
    return response


def _lead_step(approved_tool: dict[str, Any] | None) -> list[dict[str, str]]:
    if approved_tool:
        phrase = safety.describe_action(approved_tool.get("tool", ""), approved_tool.get("arguments"))
        return [_step("decide", "Approved", f"You approved: {phrase}")]
    return [_step("understand", "Conversation", "No direct command — thinking it through")]


class CognitiveKernel:
    def __init__(self, llm: Any = None, events: EventBus | None = None, planner: Planner | None = None):
        self._llm = llm
        self.events = events or default_bus
        self.planner = planner or Planner()
        self._pending: OrderedDict[str, tuple[dict[str, Any], float]] = OrderedDict()

    @property
    def llm(self) -> Any:
        if self._llm is None:
            self._llm = get_default_llm()
        return self._llm

    # ── public entry points ────────────────────────────────────────────────
    async def handle(
        self,
        text: str,
        *,
        user: Any = None,
        history: list[dict[str, str]] | None = None,
        source: str = "chat",
        approved_tool: dict[str, Any] | None = None,
        provider: str = "",
        tools_enabled: bool = True,
    ) -> LLMResponse:
        fast = await self._fast_path(text, user, history, source, approved_tool, provider, tools_enabled)
        if fast is not None:
            return fast
        response = await self.llm.ask(text, **_brain_kwargs(history, approved_tool, provider, tools_enabled))
        for step in getattr(response, "tool_steps", None) or []:
            await self._publish_step(step, user, source)
        if getattr(response, "needs_approval", False):
            self._hold(user, getattr(response, "pending_tool", None), origin="llm")
        return _set_trace(response, _brain_trace(response, _lead_step(approved_tool)))

    async def stream(
        self,
        text: str,
        *,
        user: Any = None,
        history: list[dict[str, str]] | None = None,
        source: str = "chat",
        approved_tool: dict[str, Any] | None = None,
        provider: str = "",
        tools_enabled: bool = True,
    ) -> AsyncIterator[LLMEvent]:
        fast = await self._fast_path(text, user, history, source, approved_tool, provider, tools_enabled)
        if fast is not None:
            for event in response_events(fast):
                yield event
            return
        tool_steps: list[dict[str, Any]] = []
        async for event in self.llm.stream(text, **_brain_kwargs(history, approved_tool, provider, tools_enabled)):
            if event.type == "tool" and isinstance(event.metadata, dict):
                tool_steps.append(event.metadata)
                await self._publish_step(event.metadata, user, source)
            if event.type == "done":
                meta = dict(event.metadata or {})
                if meta.get("needs_approval"):
                    self._hold(user, meta.get("pending_tool"), origin="llm")
                summary = LLMResponse(text="", provider=str(meta.get("provider") or ""), tool_steps=tool_steps,
                                      needs_approval=bool(meta.get("needs_approval")),
                                      pending_tool=meta.get("pending_tool"))
                meta["trace"] = _brain_trace(summary, _lead_step(approved_tool))
                event = LLMEvent("done", content=event.content, metadata=meta)
            yield event

    def pending_action(self, user: Any = None) -> dict[str, Any] | None:
        """The action currently held for this user's confirmation, if any."""
        key = self._user_key(user)
        entry = self._pending.get(key)
        if entry is None:
            return None
        action, created = entry
        if time.monotonic() - created > PENDING_TTL_SECONDS:
            self._pending.pop(key, None)
            return None
        return action

    # ── pipeline ───────────────────────────────────────────────────────────
    async def _fast_path(
        self,
        text: str,
        user: Any,
        history: list[dict[str, str]] | None,
        source: str,
        approved_tool: dict[str, Any] | None,
        provider: str,
        tools_enabled: bool,
    ) -> LLMResponse | None:
        """Handle what the kernel can decide itself; None means 'ask the brain'."""
        text = (text or "").strip()
        key = self._user_key(user)

        # UI "Approve": this resolves whatever was held. Kernel-held assistant
        # actions run here; anything else goes to the brain's approval flow.
        if approved_tool:
            held = self.pending_action(user)
            self._pending.pop(key, None)
            if approved_tool.get("tool") == PLAN_TOOL:
                return await self._approved_plan(approved_tool, held, user=user, source=source, prompt=text)
            denied = await self._deny_if_unprivileged(approved_tool, user, source)
            if denied is not None:
                return denied
            if approved_tool.get("origin") == KERNEL_ORIGIN and approved_tool.get("tool") in _kernel_tools():
                return await self._act(approved_tool, user=user, source=source, prompt=text,
                                       trace=_lead_step(approved_tool))
            return None

        # A spoken/typed yes or no resolves the held action. Any other message
        # means the conversation moved on, so the held action is dropped — a
        # stray "yes" later can never release it.
        pending = self.pending_action(user)
        if pending is not None:
            self._pending.pop(key, None)
            intent = confirmation_intent(text)
            phrase = safety.describe_action(pending.get("tool", ""), pending.get("arguments"))
            if intent == "affirm":
                confirmed = [_step("decide", "Confirmed", f"You confirmed: {phrase}")]
                if pending.get("tool") == PLAN_TOOL and isinstance(pending.get("plan"), dict):
                    return await self._run_plan(Plan.from_dict(pending["plan"]), user=user, source=source,
                                                prompt=text, trace=confirmed)
                denied = await self._deny_if_unprivileged(pending, user, source)
                if denied is not None:
                    return denied
                if pending.get("origin") == KERNEL_ORIGIN:
                    return await self._act(pending, user=user, source=source, prompt=text, trace=confirmed)
                llm_call = {k: v for k, v in pending.items() if k != "origin"}
                response = await self.llm.ask(text, **_brain_kwargs(history, llm_call, provider, True))
                for step in getattr(response, "tool_steps", None) or []:
                    await self._publish_step(step, user, source)
                return _set_trace(response, _brain_trace(response, confirmed))
            if intent == "deny":
                await self._emit("action.cancelled", {"tool": pending.get("tool"), "user": key, "source": source})
                return LLMResponse(text=f"Okay, I won't {phrase}.", provider=KERNEL_PROVIDER,
                                   trace=[_step("decide", "Cancelled", f"Cancelled: {phrase}")])

        if not tools_enabled or not text:
            return None

        # Understand a goal: a routine, a device group or several commands at
        # once become a plan; goal-like requests ask the brain for the steps.
        plan = self.planner.plan(text)
        if plan is None and self.planner.is_goal(text):
            plan = await self.planner.plan_with_brain(text, self.llm, provider=provider)
        if plan is not None:
            return await self._start_plan(plan, user=user, source=source, prompt=text)

        # Understand: turn a clear command into a concrete action.
        routed = route_intent(text)
        if routed is None:
            return None
        action = {"tool": routed.tool, "arguments": dict(routed.arguments), "origin": KERNEL_ORIGIN}
        understood = _step("understand", "Intent", _describe_call(routed.tool, routed.arguments))

        # Decide: risky actions need an admin, and wait for confirmation unless
        # pre-authorized.
        assessment = safety.assess(routed.tool, routed.arguments)
        denied = await self._deny_if_unprivileged(action, user, source)
        if denied is not None:
            return _set_trace(denied, [understood, *denied.trace])
        if assessment.needs_confirmation and source not in PRE_AUTHORIZED_SOURCES:
            self._hold(user, action, origin=KERNEL_ORIGIN)
            phrase = safety.describe_action(routed.tool, routed.arguments)
            await self._emit("action.pending", {"tool": routed.tool, "arguments": routed.arguments,
                                                "user": key, "source": source, "reason": assessment.reason})
            return LLMResponse(
                text=(f"Just to confirm — should I {phrase}? That {assessment.reason}. "
                      "Say yes to go ahead, or no to cancel."),
                provider=KERNEL_PROVIDER,
                needs_approval=True,
                pending_tool=action,
                trace=[understood, _step("decide", "Needs confirmation", f"That {assessment.reason}")],
            )

        # Act.
        decided = _step("decide", "Allowed",
                        "Pre-authorized by you" if assessment.needs_confirmation else "Safe to run now")
        return await self._act(action, user=user, source=source, prompt=text, trace=[understood, decided])

    async def _deny_if_unprivileged(self, action: dict[str, Any], user: Any, source: str) -> LLMResponse | None:
        """Refuse a confirmation-level action for a non-admin web user."""
        tool = str(action.get("tool") or "")
        args = action.get("arguments") or {}
        assessment = safety.assess(tool, args)
        if not assessment.needs_confirmation or _is_privileged(user, source):
            return None
        phrase = safety.describe_action(tool, args)
        await self._emit("action.denied", {"tool": tool, "user": self._user_key(user),
                                           "source": source, "reason": assessment.reason})
        return LLMResponse(
            text=f"Sorry — only an admin can {phrase}. That {assessment.reason}.",
            provider=KERNEL_PROVIDER,
            trace=[_step("decide", "Refused", f"Admin only — that {assessment.reason}")],
        )

    async def _act(
        self,
        action: dict[str, Any],
        *,
        user: Any,
        source: str,
        prompt: str,
        trace: list[dict[str, str]] | None = None,
    ) -> LLMResponse:
        tool = str(action.get("tool") or "")
        args = dict(action.get("arguments") or {})
        step = await self._execute(tool, args)
        ok = bool(step.get("success"))
        text = step.get("output") if ok else f"I couldn't do that — {step.get('error') or 'the tool failed'}."
        text = text or "Done."
        steps = [*(trace or []), _step("act", "Action" if ok else "Action failed", text)]
        # Remember what was done, and let the rest of the system react to it.
        if await self._remember(prompt or safety.describe_action(tool, args), text):
            steps.append(_step("remember", "Memory", "Saved to memory"))
        await self._emit("action.executed", {"tool": tool, "arguments": args, "success": ok,
                                             "source": source, "user": self._user_key(user), "result": text[:500]})
        return LLMResponse(text=text, provider=KERNEL_PROVIDER, tool_steps=[step], trace=steps)

    # ── plans ──────────────────────────────────────────────────────────────
    async def start_plan(self, plan: Plan, *, user: Any = None, source: str = "chat") -> LLMResponse:
        """Run a plan (e.g. a routine started from the UI) with the usual safety rules."""
        return await self._start_plan(plan, user=user, source=source, prompt=plan.goal)

    async def _start_plan(self, plan: Plan, *, user: Any, source: str, prompt: str) -> LLMResponse:
        """Run a plan now, or hold it for one confirmation if a step is risky."""
        planned = _step("plan", "Plan", f"{plan.title}: {len(plan.steps)} steps ({plan.source})")
        risky = [(i, s, safety.assess(s.tool, s.arguments)) for i, s in enumerate(plan.steps, 1)]
        risky = [(i, s, a) for i, s, a in risky if a.needs_confirmation]
        if risky and source not in PRE_AUTHORIZED_SOURCES and _is_privileged(user, source):
            key = self._user_key(user)
            action = {"tool": PLAN_TOOL, "arguments": plan.summary(), "origin": KERNEL_ORIGIN}
            self._hold(user, {**action, "plan": plan.to_dict()}, origin=KERNEL_ORIGIN)
            await self._emit("action.pending", {"tool": PLAN_TOOL, "arguments": plan.summary(), "user": key,
                                                "source": source, "reason": risky[0][2].reason})
            flagged = {i: a.reason for i, _, a in risky}
            lines = [f"{i}. {s.command}" + (f" — that {flagged[i]}" if i in flagged else "")
                     for i, s in enumerate(plan.steps, 1)]
            return LLMResponse(
                text=f"Here's my plan for “{plan.title}”:\n" + "\n".join(lines)
                     + "\nShould I go ahead? Say yes or no.",
                provider=KERNEL_PROVIDER,
                needs_approval=True,
                pending_tool=action,
                trace=[planned, _step("decide", "Needs confirmation",
                                      f"Step {risky[0][0]} {risky[0][2].reason}")],
            )
        return await self._run_plan(plan, user=user, source=source, prompt=prompt, trace=[planned])

    async def _approved_plan(self, approved: dict[str, Any], held: dict[str, Any] | None, *,
                             user: Any, source: str, prompt: str) -> LLMResponse:
        """UI Approve for a plan: run the plan the kernel held, never a client-edited one."""
        approved_trace = [_step("decide", "Approved", "You approved the plan")]
        if held and held.get("tool") == PLAN_TOOL and isinstance(held.get("plan"), dict):
            return await self._run_plan(Plan.from_dict(held["plan"]), user=user, source=source,
                                        prompt=prompt, trace=approved_trace)
        # The hold expired: rebuild from the plain commands, each re-understood.
        args = approved.get("arguments") or {}
        steps = []
        for command in args.get("steps") or []:
            found = steps_for_clause(str(command))
            if not found:
                return LLMResponse(text="That plan has expired — please ask me again.", provider=KERNEL_PROVIDER,
                                   trace=[_step("decide", "Expired", "The held plan expired")])
            steps.extend(found)
        plan = Plan(goal=str(args.get("goal") or prompt), title=str(args.get("title") or "your plan"),
                    source="approved", steps=steps)
        return await self._run_plan(plan, user=user, source=source, prompt=prompt, trace=approved_trace)

    async def _run_plan(self, plan: Plan, *, user: Any, source: str, prompt: str,
                        trace: list[dict[str, str]] | None = None) -> LLMResponse:
        """Run each step through safety and the tools, then check it worked."""
        key = self._user_key(user)
        steps_trace = list(trace or [])
        privileged = _is_privileged(user, source)
        total = len(plan.steps)
        await self._emit("plan.started", {"title": plan.title, "goal": plan.goal, "source": source,
                                          "user": key, "steps": [s.command for s in plan.steps]})
        tool_steps: list[dict[str, Any]] = []
        lines: list[str] = []
        for i, step in enumerate(plan.steps, 1):
            assessment = safety.assess(step.tool, step.arguments)
            phrase = safety.describe_action(step.tool, step.arguments)
            if assessment.needs_confirmation and not privileged:
                step.status, step.result = "skipped", f"only an admin can {phrase}"
                lines.append(f"Skipped: {phrase} (only an admin can do that).")
                steps_trace.append(_step("decide", f"Step {i}/{total} skipped", f"Admin only — {phrase}"))
                continue
            result = await self._execute(step.tool, dict(step.arguments))
            output = str(result.get("output") or result.get("error") or "")
            ok = bool(result.get("success")) and not looks_failed(output)
            check = None
            if ok:  # did the device really change? (the tool saying so isn't proof)
                verified, detail = await verify_step(step)
                step.verified = verified
                if verified is not None:
                    check = _step("check", "Checked" if verified else "Check failed", detail)
                if verified is False:
                    ok = False
                    output = f"{output} But when I checked, {detail}."
            step.status, step.result = ("done" if ok else "failed"), output
            tool_steps.append({**result, "success": ok})
            lines.append(output if ok else f"Couldn't {phrase}: {output}")
            steps_trace.append(_step("act", f"Step {i}/{total}" if ok else f"Step {i}/{total} failed", output))
            if check:
                steps_trace.append(check)
            await self._emit("action.executed", {"tool": step.tool, "arguments": step.arguments, "success": ok,
                                                 "source": source, "user": key, "result": output[:500],
                                                 "plan": plan.title})
            await self._emit("plan.step", {"title": plan.title, "index": i, "total": total,
                                           "command": step.command, "success": ok, "user": key})
        done = sum(1 for s in plan.steps if s.status == "done")
        heading = (f"{plan.title} — all {total} steps done." if done == total
                   else f"{plan.title} — {done} of {total} steps done.")
        text = heading + "\n" + "\n".join(lines)
        if await self._remember(prompt or plan.goal, text):
            steps_trace.append(_step("remember", "Memory", "Saved to memory"))
        await self._emit("plan.completed", {"title": plan.title, "goal": plan.goal, "done": done, "total": total,
                                            "failed": sum(1 for s in plan.steps if s.status == "failed"),
                                            "user": key, "source": source})
        return LLMResponse(text=text, provider=KERNEL_PROVIDER, tool_steps=tool_steps, trace=steps_trace)

    async def _execute(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        if isinstance(self.llm, AtulyaLLM) and self.llm.tools.get(tool) is not None:
            return await self.llm.run_tool({"tool": tool, "arguments": args})
        from atulya.agent.tools import execute_tool  # brains without the unified registry

        out = await execute_tool(tool, **args)
        failed = out.startswith("Error")
        return {"tool": tool, "arguments": args, "success": not failed,
                "output": "" if failed else out, "error": out if failed else ""}

    async def _publish_step(self, step: dict[str, Any], user: Any, source: str) -> None:
        """Publish a tool the brain ran natively, so triggers see it too."""
        await self._emit("action.executed", {
            "tool": step.get("tool"), "arguments": step.get("arguments") or {},
            "success": bool(step.get("success")), "source": source, "user": self._user_key(user),
            "result": str(step.get("output") or step.get("error") or "")[:500], "via": "brain",
        })

    async def _remember(self, prompt: str, text: str) -> bool:
        """Write to long-term memory; True when the brain actually keeps memory."""
        if isinstance(self.llm, AtulyaLLM) and self.llm.use_memory:
            try:
                await self.llm.remember(prompt, text)
                return True
            except Exception as exc:  # noqa: BLE001 - memory is best-effort
                logger.debug("kernel memory write failed: %s", exc)
        return False

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            await self.events.emit(event_type, payload)
        except Exception as exc:  # noqa: BLE001 - events are best-effort
            logger.debug("kernel event emit failed: %s", exc)

    def _hold(self, user: Any, action: dict[str, Any] | None, *, origin: str) -> None:
        if not action:
            return
        key = self._user_key(user)
        self._pending[key] = ({**action, "origin": action.get("origin", origin)}, time.monotonic())
        self._pending.move_to_end(key)
        while len(self._pending) > _MAX_PENDING:
            self._pending.popitem(last=False)

    @staticmethod
    def _user_key(user: Any) -> str:
        if isinstance(user, dict):
            return str(user.get("username") or "default")
        return str(user or "default")


def response_events(response: LLMResponse) -> list[LLMEvent]:
    """Render a finished response as the same event sequence the brain streams."""
    events = [LLMEvent("tool", metadata=step) for step in response.tool_steps]
    events += [LLMEvent("token", content=chunk) for chunk in _chunk_text(response.text)]
    meta: dict[str, Any] = {"provider": response.provider, "steps": response.tool_steps, "trace": response.trace}
    if response.needs_approval:
        pending = response.pending_tool or {}
        meta.update({"needs_approval": True, "pending_tool": pending,
                     "tool": pending.get("tool"), "tool_args": pending.get("arguments", {})})
    events.append(LLMEvent("done", metadata=meta))
    return events


_KERNELS: OrderedDict[int, tuple[Any, CognitiveKernel]] = OrderedDict()


def get_kernel(llm: Any = None) -> CognitiveKernel:
    """The kernel wrapping ``llm`` (default brain if None); one per brain instance."""
    llm = llm if llm is not None else get_default_llm()
    entry = _KERNELS.get(id(llm))
    if entry is not None and entry[0] is llm:
        return entry[1]
    kernel = CognitiveKernel(llm=llm)
    _KERNELS[id(llm)] = (llm, kernel)
    while len(_KERNELS) > 8:
        _KERNELS.popitem(last=False)
    return kernel
