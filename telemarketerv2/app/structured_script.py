"""
Structured 5-step / 16-sub-step script loader for Version A (Scripted AI Voice Clone).

Uses 5_Steps_Marketing_Updated.md as the source of content. Segments are defined
here to match the script structure for deterministic delivery and branching.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ScriptSegment:
    """One deliverable block: step, sub_step, label, and lines to speak."""
    step: int
    sub_step: int
    label: str
    lines: List[str]
    branch_positive: Optional[Tuple[int, int]] = None
    branch_negative: Optional[Tuple[int, int]] = None
    branch_more_info: Optional[Tuple[int, int]] = None
    objection_lines: Optional[List[str]] = None
    email_exit_lines: Optional[List[str]] = None


def _speech(lines: List[str]) -> str:
    return " ".join(l.strip() for l in lines if l.strip())


# 5 main steps, 16 sub-steps — content from 5_Steps_Marketing_Updated.md
STRUCTURED_SEGMENTS: List[ScriptSegment] = [
    # STEP 1 -- INTRODUCTION
    ScriptSegment(1, 1, "A -- Gatekeeper", [
        "Hi, can I speak to the owner please?",
        "It's nothing serious. It's just a quick introductory call.",
    ]),
    ScriptSegment(1, 2, "B -- Relax the Prospect", [
        "Hi. It's nothing serious.",
    ]),
    ScriptSegment(1, 3, "C -- Reason for Contact", [
        "It's just a quick introductory call. I wanted to give you the chance to see some information on how to reduce costs in your business.",
        "My name's Jay from Proactiv. Sorry, who am I speaking with?",
    ]),
    ScriptSegment(1, 4, "D -- CREATE INTEREST", [
        "Proactiv have been established since 2009. We've developed several unique concepts that help businesses: reduce overheads, increase word-of-mouth referrals, eliminate advertising costs. It's genuinely a game-changer.",
    ]),
    ScriptSegment(1, 5, "D -- PRE-CLOSE (Checkpoint #1)", [
        "That sounds pretty interesting, I'm sure you'd agree?",
    ], branch_positive=(4, 1), branch_negative=(1, 6), branch_more_info=(2, 1),
      objection_lines=[
          "I completely appreciate that — I wouldn't expect you to be overly interested from such a brief introduction.",
          "Let me just ask you something quickly — Every business likes saving money, right?",
      ],
      email_exit_lines=[
          "All I'm really looking to do is send you some information by email about reducing overheads. Would you be open to receiving that?",
      ]),
    ScriptSegment(1, 6, "D -- IF NOT INTERESTED (objection)", [
        "I completely appreciate that — I wouldn't expect you to be overly interested from such a brief introduction.",
        "Let me just ask you something quickly — Every business likes saving money, right?",
    ], email_exit_lines=[
        "All I'm really looking to do is send you some information by email about reducing overheads. Would you be open to receiving that?",
    ]),
    ScriptSegment(1, 7, "D -- IF WHAT IS IT (more info)", [
        "I understand — I've been quite brief. All I'm looking to do is quickly run the information by you and, if you like the sound of it, give you the chance to see some FREE samples. We don't send junk mail.",
        "I've just got a couple of quick questions so I can see which concept is most relevant.",
    ]),
    # STEP 2 -- PRESENTATION
    ScriptSegment(2, 1, "E -- Qualify", [
        "Could you handle more customers in your business?",
    ]),
    ScriptSegment(2, 2, "F -- Highlight Problem", [
        "Government statistics state 25.3% of MOTs are carried out late in the UK.",
    ]),
    ScriptSegment(2, 3, "G -- Fact Find", [
        "Do you currently have anything in place to help customers remember their MOT due date?",
        "I'm sure you'd agree word-of-mouth is the best way to attract new customers?",
    ]),
    # STEP 3 -- EXPLANATION
    ScriptSegment(3, 1, "Story 1 -- Why Cards Are KEPT", [
        "Plastic cards look and feel like credit cards. They are durable, perceived as valuable, and kept in wallets.",
    ]),
    ScriptSegment(3, 2, "Story 1 -- Pre-Close", [
        "They sound like a good idea, I'm sure you'd agree?",
    ]),
    ScriptSegment(3, 3, "Story 2 -- Referral Tracking", [
        "Cards get passed on. You can monitor referrals and reward customers.",
    ]),
    ScriptSegment(3, 4, "Story 2 -- Pre-Close", [
        "It sounds like a strong concept, doesn't it?",
    ]),
    ScriptSegment(3, 5, "Story 3 -- Key Fob Comparison", [
        "Solid plastic fobs last 5 to 6 years versus laminated versions that peel. Makes sense why solid lasts longer, right?",
    ]),
    ScriptSegment(3, 6, "Story 4 -- Writable MOT Reminder", [
        "Writable coating allows MOT due date reminders on customer keys.",
    ]),
    # STEP 4 -- CLOSE
    ScriptSegment(4, 1, "Master Pre-Close", [
        "Overall, it sounds like a pretty solid idea for a garage like yours, yeah?",
    ]),
    ScriptSegment(4, 2, "Explain How We Work", [
        "We show business owners samples over camera. 10 to 15 minutes. No travel required.",
    ]),
    ScriptSegment(4, 3, "Assumptive Close", [
        "I've got availability later today or tomorrow. Which works better for you?",
    ]),
    # STEP 5 -- CONSOLIDATION
    ScriptSegment(5, 1, "Confirm Decision Makers", [
        "Is anyone else involved in making this decision?",
    ]),
    ScriptSegment(5, 2, "Confirm Contact Details", [
        "So your full name is? And I have the business name and address? Let me confirm mobile and email for the confirmation.",
    ]),
    ScriptSegment(5, 3, "Prepare for Next Stage", [
        "You'll get a text or a quick call to remind you on the day of the appointment, and we'll email you a link for the video call.",
    ]),
    ScriptSegment(5, 4, "Farewell", [
        "It's been great speaking with you. We look forward to speaking tomorrow. Enjoy the rest of your day.",
    ]),
]


class StructuredScript:
    """
    Structured 5-step / 16-sub-step script for deterministic (Version A) delivery.
    """

    def __init__(self, script_path: Optional[str] = None):
        self.script_path = Path(script_path) if script_path else None
        self.segments = list(STRUCTURED_SEGMENTS)
        logger.info("StructuredScript loaded %d segments (5 steps, 16+ sub-steps)", len(self.segments))

    def get_segment_by_index(self, index: int) -> Optional[ScriptSegment]:
        if 0 <= index < len(self.segments):
            return self.segments[index]
        return None

    def get_first_segment(self) -> Optional[ScriptSegment]:
        return self.get_segment_by_index(0)

    def get_speech_for_segment(self, segment: ScriptSegment) -> str:
        return _speech(segment.lines)

    def get_next_segment(
        self,
        current: ScriptSegment,
        user_sentiment: str,
    ) -> Optional[ScriptSegment]:
        if user_sentiment == "positive" and current.branch_positive:
            step, sub = current.branch_positive
            return self._segment_at(step, sub)
        if user_sentiment == "negative" and current.branch_negative:
            step, sub = current.branch_negative
            return self._segment_at(step, sub)
        if user_sentiment == "more_info" and current.branch_more_info:
            step, sub = current.branch_more_info
            return self._segment_at(step, sub)
        idx = next((i for i, s in enumerate(self.segments) if s is current), -1)
        if idx >= 0 and idx + 1 < len(self.segments):
            return self.segments[idx + 1]
        return None

    def _segment_at(self, step: int, sub: int) -> Optional[ScriptSegment]:
        for seg in self.segments:
            if seg.step == step and seg.sub_step == sub:
                return seg
        for seg in self.segments:
            if seg.step == step:
                return seg
        return None

    def get_objection_response(self, segment: ScriptSegment) -> Optional[str]:
        if segment.objection_lines:
            return _speech(segment.objection_lines)
        return None

    def get_email_exit_response(self, segment: ScriptSegment) -> Optional[str]:
        if segment.email_exit_lines:
            return _speech(segment.email_exit_lines)
        return None


_default_script: Optional[StructuredScript] = None


def get_structured_script(script_path: Optional[str] = None) -> StructuredScript:
    """Return the structured script (cached)."""
    global _default_script
    if _default_script is None:
        path = script_path or str(
            Path(__file__).resolve().parent.parent / "data" / "scripts" / "5_Steps_Marketing_Updated.md"
        )
        _default_script = StructuredScript(path)
    return _default_script
