# AI Telemarketer Script: Making Money Focus (v1.3 - New Intro)

# STATE: INITIAL_GREETING_SEQUENCE
Action: CUSTOM_LOGIC_INITIAL_GREETING
# Dialogue variants chosen by Python logic:
Dialogue_with_name: Hi can I speak to {{owner_first_name}} please?
Dialogue_no_name: Hi can I speak to the owner please?
Next States: AWAIT_INITIAL_RESPONSE

---

# STATE: AWAIT_INITIAL_RESPONSE
# Action: LISTEN
Next States: OWNER_ON_PHONE_REINTRODUCE, EXPLAIN_CALL_INTRODUCTORY, PITCH_INTEREST_TO_GATEKEEPER, AWAIT_OWNER_AVAILABILITY_RESPONSE, HANGUP_MM
# e.g., User: "Yes, speaking" / "Yes, I am the owner" -> OWNER_ON_PHONE_REINTRODUCE
# e.g., User: "What's it regarding?" -> EXPLAIN_CALL_INTRODUCTORY
# e.g., User: "I'll get them" -> CONFIRM_OWNER_COMING_TO_PHONE
# e.g., User: "They're not here" -> PITCH_INTEREST_TO_GATEKEEPER

---

# STATE: EXPLAIN_CALL_INTRODUCTORY
Dialogue: Oh, it's nothing serious, it's just a quick introductory call. My name is Isaac from Pro Active. Is the owner there?
# Alternative Dialogue (if AI needs variety or more directness): Is the owner around today?
Action: LISTEN
Next States: AWAIT_OWNER_AVAILABILITY_RESPONSE

---

# STATE: AWAIT_OWNER_AVAILABILITY_RESPONSE
# Action: LISTEN
Next States: CONFIRM_OWNER_COMING_TO_PHONE, OWNER_ON_PHONE_REINTRODUCE, PITCH_INTEREST_TO_GATEKEEPER, HANGUP_MM
# e.g., User: "I'll get them" -> CONFIRM_OWNER_COMING_TO_PHONE
# e.g., User: "They're not here" / "Can I take a message?" -> PITCH_INTEREST_TO_GATEKEEPER
# e.g., Owner comes to phone -> OWNER_ON_PHONE_REINTRODUCE

---

# STATE: PITCH_INTEREST_TO_GATEKEEPER
Dialogue: We're a well-established UK company called Proactiv. We work closely with {{ business_category | default: 'independent businesses' }}. We've got some great ways to show you how to reduce overheads, and at the same time, we've got some great ways to show you how to increase profits for free. But yeah, just need to run it by the owner if they're around today.
Action: LISTEN
# Python logic will decide if AI should ask "Is the owner around today?" again if not clear from context.
Next States: AWAIT_GATEKEEPER_DECISION_AFTER_PITCH, SCHEDULE_CALLBACK_MM, HANGUP_MM

---

# STATE: AWAIT_GATEKEEPER_DECISION_AFTER_PITCH
# Action: LISTEN
# Next States: SCHEDULE_CALLBACK_MM, HANGUP_MM, CONFIRM_OWNER_COMING_TO_PHONE
# e.g., Gatekeeper: "When can you call back?" -> SCHEDULE_CALLBACK_MM
# e.g., Gatekeeper: "They're not interested." -> HANGUP_MM (or a softer gatekeeper decline)
# e.g., Gatekeeper: "Okay, I'll see if they're free." -> CONFIRM_OWNER_COMING_TO_PHONE

---

# STATE: CONFIRM_OWNER_COMING_TO_PHONE
Dialogue: Okay, thank you.
Action: TALK_PAUSE
Next States: OWNER_ON_PHONE_REINTRODUCE

---

# STATE: OWNER_ON_PHONE_REINTRODUCE
Dialogue: Great! it's nothing serious, I'ts just a quick introductury call, My name is Isaac from Pro Active. Sorry, who am I speaking with?
Action: LISTEN
Next States: ACKNOWLEDGE_OWNER_NAME_AND_GREET

---

# STATE: ACKNOWLEDGE_OWNER_NAME_AND_GREET
Dialogue: Oh, Hi {{ state_machine.owner_name | default("") }}, lovely to meet you.
Action: TALK
Next States: PITCH_INTEREST_TO_OWNER

---

# STATE: PITCH_INTEREST_TO_OWNER
# This is the main "create interest" line for the owner.
# It reuses elements from the old INTRO_PROACTIV_MM but is framed by the new intro.
Dialogue: Our Managing Director has over 30 years' experience supporting independent businesses like yours. He's developed several unique concepts that both increase customer base and reduce overheads. His most recent invention helps bring in more customers through word-of-mouth, for FREE. He found and addressed the main reasons why only a small percentage of people act on word-of-mouth recommendations and why that figure has been dropping. The results for businesses like yours have been spectacular. It's a real game-changer. Sounds pretty interesting, doesn't it?
Action: LISTEN
Next States: AWAIT_POST_INTEREST_PITCH_RESPONSE

---

# STATE: AWAIT_POST_INTEREST_PITCH_RESPONSE
# Action: LISTEN
Next States: SCRIPT_SELECTION_MM, PITCH_APPOINTMENT_MM, HANDLE_OBJECTION_MM, NOT_INTERESTED_MM
# If "Yes" or "Tell me more" or sounds positive -> SCRIPT_SELECTION_MM (to ask MM or SM focus)
# If strong positive and wants demo -> PITCH_APPOINTMENT_MM
# If "No" or "Not interested" -> NOT_INTERESTED_MM (or a softer objection handler first)
# If "What is it?" type response -> CLARIFICATION_MM (if still needed after the pitch)

---

# STATE: SCRIPT_SELECTION_MM
Dialogue: What's most important for your business right now - bringing in more customers or reducing costs?
Action: LISTEN
Next States: INTRO_RESPONSE_MM, REDIRECT_TO_SAVING, HANDLE_OBJECTION_MM, CLARIFICATION_MM, NOT_INTERESTED_MM
# INTRO_RESPONSE_MM might be deprecated or its content merged elsewhere or renamed e.g., HANDLE_MM_FOCUS_RESPONSE

---

# STATE: REDIRECT_TO_SAVING
Dialogue: It sounds like reducing costs is a priority for you right now. Our Managing Director has actually developed several concepts specifically designed to improve cashflow and reduce overheads for businesses just like yours. Would it be helpful if I focused more on those solutions?
Action: LISTEN
Next States: SWITCH_TO_SAVING_SCRIPT, INTRO_RESPONSE_MM, HANDLE_OBJECTION_MM, NOT_INTERESTED_MM
# INTRO_RESPONSE_MM here should likely be a state in the SM script path if they agree to switch.

---

# STATE: SWITCH_TO_SAVING_SCRIPT
# This is a special state that signals to switch to the saving money script
Dialogue: Great, let me tell you about our cost-saving solutions instead.
Action: SWITCH_SCRIPT
Target Script: saving_money_script.md
Target State: INTRO_PROACTIV_SM # Or a more appropriate entry point in SM script after switching

---

# STATE: INTRO_RESPONSE_MM
# This state's purpose needs re-evaluation.
# If after SCRIPT_SELECTION_MM they choose "more customers", this state is hit.
# The original dialogue was: "What aspects of that approach might be most beneficial for your business?"
# This might now directly lead to PITCH_APPOINTMENT_MM or a more focused benefit discussion.
Dialogue: Okay, focusing on bringing in more customers. What aspects of boosting word-of-mouth referrals for free sound most appealing to you?
Action: LISTEN
Next States: BUSINESS_DISCOVERY_MM, PRE_CLOSE_INTEREST_MM, HANDLE_OBJECTION_MM, CLARIFICATION_MM, NOT_INTERESTED_MM
# BUSINESS_DISCOVERY_MM and PRE_CLOSE_INTEREST_MM might be too early if we just pitched.
# Perhaps this state should be more about gauging specific interest points before PITCH_APPOINTMENT_MM

---

# STATE: BUSINESS_DISCOVERY_MM
Dialogue: Before I explain more specifically, may I ask what kind of business you're in and what your biggest challenges are right now? This will help me tailor the information to your industry and specific needs.
Action: LISTEN
Next States: BUSINESS_RESPONSE_MM, REDIRECT_TO_SAVING, CLARIFICATION_MM, NOT_INTERESTED_MM

---

# STATE: BUSINESS_RESPONSE_MM
Dialogue: Thank you for sharing that. For businesses in your industry, our approach has been particularly effective. We've seen companies similar to yours increase their customer base by 15-30% through improved word-of-mouth referrals, without increasing their marketing budget. Would you be interested in learning specifically how this could work for your business?
Action: LISTEN
Next States: PRE_CLOSE_INTEREST_MM, HANDLE_OBJECTION_MM, CLARIFICATION_MM, NOT_INTERESTED_MM

---

# STATE: PRE_CLOSE_INTEREST_MM
Dialogue: It sounds pretty interesting, I'm sure you'd agree?
Action: TALK
# Next state should be more decisive based on this.
Next States: PITCH_APPOINTMENT_MM # Direct attempt to book.

---

# STATE: PITCH_APPOINTMENT_MM
Dialogue: Fantastic. The best way to see how this could work specifically for your business is with a quick ten to fifteen minute remote demonstration. We can show you the concept and discuss the potential impact. Would you be open to scheduling that sometime this week or next?
Action: LISTEN
Next States: BOOK_APPOINTMENT_MM, HANDLE_OBJECTION_MM, PITCH_WAMAILER_MM, NOT_INTERESTED_MM

---

# STATE: CLARIFICATION_MM
Dialogue: I understand you'd like more information. Our service specifically helps businesses like yours attract more customers without spending on advertising. We've developed a unique system that increases word-of-mouth recommendations by addressing the psychological barriers that prevent people from referring others. Would you like to hear how this could work for your specific business?
Action: TALK
Next States: CLARIFICATION_RESPONSE_MM

---

# STATE: CLARIFICATION_RESPONSE_MM
Dialogue: Does that help clarify what we're offering? I'd be happy to explain more about how this might benefit your specific business.
Action: LISTEN
Next States: PRE_CLOSE_INTEREST_MM, HANDLE_OBJECTION_MM, NOT_INTERESTED_MM # PRE_CLOSE_INTEREST_MM might be redundant if this leads back to the main pitch benefits.

---
# --- Remaining states from original script (need review for integration) ---

# STATE: GATEKEEPER_DETECTED_MM # This concept is now handled by the new intro flow. May be deprecated.
# Dialogue: Okay, thank you. Could you let the owner know Isaac from Proactiv called regarding some concepts proven to increase customer base? When would be a good time for me to call back to speak with them directly?
# Action: LISTEN
# Next States: SCHEDULE_CALLBACK_MM, HANGUP_MM

---

# STATE: INTRO_PROACTIV_MM # Content merged into PITCH_INTEREST_TO_OWNER. May be deprecated.
# Dialogue: Great. Our Managing Director has over 30 years' experience supporting independent businesses...
# Action: TALK
# Next States: SCRIPT_SELECTION_MM, CLARIFICATION_MM, HANDLE_OBJECTION_MM, NOT_INTERESTED_MM

---
# ... (Keep other existing states like HANDLE_OBJECTION variants, BOOK_APPOINTMENT, PITCH_WAMAILER etc.)
# ... (These will be entered after the new AWAIT_POST_INTEREST_PITCH_RESPONSE or SCRIPT_SELECTION_MM)

# Ensure all paths lead to a HANGUP or loop back correctly.
# Review all Next States lists for consistency with the new flow.

# STATE: HANDLE_OBJECTION_MM
Dialogue: I understand you might need more clarity. Our Managing Director has developed a unique system that dramatically increases word-of-mouth referrals for businesses, which is the most powerful form of marketing. This approach has helped businesses like yours increase their customer base without spending on expensive advertising. Would scheduling a brief 10-15 minute demonstration make sense to learn more?
Action: LISTEN
Next States: BOOK_APPOINTMENT_MM, HANDLE_OBJECTION_BUSY_NOW_MM, HANDLE_OBJECTION_BUSY_BUSINESS_MM, HANDLE_OBJECTION_BUSY_APPOINTMENT_MM, HANDLE_OBJECTION_NI_MM, CLARIFICATION_MM, PITCH_WAMAILER_MM

---

# STATE: HANDLE_OBJECTION_NI_MM
Dialogue: Okay, I understand this might not seem relevant right now. Just to confirm, finding new ways to bring in customers for free isn't a priority for you at the moment?
Action: LISTEN
Next States: PITCH_APPOINTMENT_MM, PITCH_WAMAILER_MM, HANGUP_NI_MM

---

# STATE: HANDLE_OBJECTION_BUSY_NOW_MM
Dialogue: I appreciate you're busy running your business, and I've called you out of the blue. I also appreciate you probably need more information. The way we work is a quick 10-15 minute remote demo to show you exactly how it operates. Could we schedule that for a better time, perhaps later today or tomorrow?
Action: LISTEN
Next States: BOOK_APPOINTMENT_MM, PITCH_WAMAILER_MM, NOT_INTERESTED_MM

---

# STATE: HANDLE_OBJECTION_BUSY_BUSINESS_MM
Dialogue: That's actually great to hear your business is doing well! Do you see that remaining the same for the foreseeable future? [Pause for answer] Excellent. While attracting new customers is key, we've also developed concepts to improve cashflow and reduce overheads. Saving money is as good as generating revenue, I'm sure you'd agree? Perhaps seeing how we do that would be beneficial too? The demo still only takes 10-15 minutes.
Action: LISTEN
Next States: BOOK_APPOINTMENT_MM, PITCH_WAMAILER_MM, NOT_INTERESTED_MM

---

# STATE: HANDLE_OBJECTION_BUSY_APPOINTMENT_MM
Dialogue: I understand you're running a busy business. We primarily work with independent business owners like yourself, so our appointments are designed specifically for busy schedules. That's why we keep them brief, just 10 to 15 minutes, and conduct them remotely via video call, making them very flexible. We can usually fit them in anytime between 8 am and 8:30 pm, including evenings or weekends if that helps.
Action: TALK
Next States: PRE_CLOSE_APPOINTMENT_MM

---

# STATE: PRE_CLOSE_APPOINTMENT_MM
Dialogue: I am sure it's worth finding just 15 minutes to learn about a potential way to never have to advertise again while bringing in lots of new customers for FREE? What time might work for that brief chat?
Action: LISTEN
Next States: BOOK_APPOINTMENT_MM, PITCH_WAMAILER_MM, NOT_INTERESTED_MM

---

# STATE: BOOK_APPOINTMENT_MM
Dialogue: Fantastic! What day and time works best for you for that brief 10-15 minute online demo?
Action: LISTEN
Next States: CONFIRM_APPOINTMENT_MM, CALLBACK_REQUESTED_MM, PITCH_WAMAILER_MM

---

# STATE: CONFIRM_APPOINTMENT_MM
Dialogue: Okay, great. I have you down for [Appointment Day] at [Appointment Time]. I'll send over a calendar invitation with the video link right away. Thanks very much for your time today, and have a great rest of your day!
Action: HANGUP
Next States:

---

# STATE: PITCH_WAMAILER_MM
Dialogue: Okay, I appreciate you're busy or perhaps not ready to commit to a time right now. We do have a WhatsApp business account and have prepared an information pack that covers the concept. Would you like me to send that over to your mobile via WhatsApp?
Action: LISTEN
Next States: GET_WAMAILER_DETAILS_MM, PITCH_EMAILER_MM, NOT_INTERESTED_MM

---

# STATE: GET_WAMAILER_DETAILS_MM
Dialogue: Great. Can I confirm the best mobile number to send the WhatsApp info pack to? [Listen and confirm number]. Okay, I'll send that across shortly. It also includes details on some fantastic introductory offers we run annually – we offer 50 businesses in each county a massive discount for helping us create awareness through their positive results. These offers often include discounts up to 50% and tend to get claimed within 24-48 hours based on past experience. There's a free phone number and email in the pack if you're interested after reviewing it.
Action: LISTEN
Next States: CONFIRM_WAMAILER_MM

---

# STATE: CONFIRM_WAMAILER_MM
Dialogue: Perfect, I've made a note to send that WhatsApp pack over to [Confirmed Mobile Number]. Thanks again for your time today. Goodbye.
Action: HANGUP
Next States:

---

# STATE: PITCH_EMAILER_MM
Dialogue: No problem. Alternatively, I could email that information pack over to you if that's easier?
Action: LISTEN
Next States: GET_EMAIL_DETAILS_MM, NOT_INTERESTED_MM, HANGUP_MM

---

# STATE: GET_EMAIL_DETAILS_MM
Dialogue: Sure thing. What's the best email address to send the information pack and offer details to? [Listen and confirm email].
Action: LISTEN
Next States: CONFIRM_EMAILER_MM

---

# STATE: CONFIRM_EMAILER_MM
Dialogue: Excellent, I'll email the pack across shortly. Thank you for your time. Goodbye.
Action: HANGUP
Next States:

---

# STATE: CALLBACK_REQUESTED_MM
Dialogue: Absolutely. When would be a more convenient time for me to call you back?
Action: LISTEN
Next States: SCHEDULE_CALLBACK_MM, NOT_INTERESTED_MM

---

# STATE: SCHEDULE_CALLBACK_MM
Dialogue: Okay, could you give me a specific day and time that works best?
Action: LISTEN
Next States: CONFIRM_CALLBACK_MM, NOT_INTERESTED_MM

---

# STATE: CONFIRM_CALLBACK_MM
Dialogue: Got it. I'll call you back on [Callback Day] around [Callback Time]. Thanks very much. Goodbye.
Action: HANGUP
Next States:

---

# STATE: DECLINE_MM
Dialogue: Okay, no problem at all. Thanks for letting me know straight away. Have a great day. Goodbye.
Action: HANGUP
Next States:

---

# STATE: NOT_INTERESTED_MM
Dialogue: Okay, I understand this isn't the right fit for you at the moment. Thank you for your time today. Have a great day. Goodbye.
Action: HANGUP
Next States:

---

# STATE: HANGUP_NI_MM
Dialogue: Understood. It sounds like this isn't a priority for you now. Thanks for your time. Goodbye.
Action: HANGUP
Next States:

---

# STATE: HANGUP_MAX_REPEATS # Added state
Dialogue: Sorry, I seem to be having trouble hearing you clearly. I'll have to end the call for now. Goodbye.
Action: HANGUP
Next States:

---

# STATE: FALLBACK_HANGUP # Added state
Dialogue: I seem to have encountered a technical difficulty. Thank you for your time. Goodbye.
Action: HANGUP
Next States:

---

# STATE: ASK_CLARIFICATION # Added state
Dialogue: Sorry, I didn't quite understand that. Could you please rephrase?
Action: TALK
Next States: AWAIT_CLARIFICATION_RESPONSE # Need a state to listen after asking

---

# STATE: AWAIT_CLARIFICATION_RESPONSE # Added state
# Action: LISTEN
# This state needs Python logic in LLMHandler to re-evaluate the user's
# rephrased response against the transitions of the *original* state
# that triggered the clarification.
# This requires passing context about the original state.
# For now, let's just define it and assume it leads back to common handlers.
Next States: HANDLE_OBJECTION_MM, SCRIPT_SELECTION_MM, NOT_INTERESTED_MM, HANGUP_MM

---

# STATE: HANGUP_MM
Dialogue: Okay, thank you for your time. Goodbye.
Action: HANGUP
Next States:

---

# STATE: ERROR_STATE_MM
Dialogue: Apologies, I seem to be having some technical issues. I'll need to end the call now. Goodbye.
Action: HANGUP
Next States:

---

# STATE: ERROR_HANDLE # Keep this as a generic error handler
Dialogue: I apologize, but I'm experiencing some technical difficulties. Let me end this call and we can try again another time. Thank you for your understanding. Goodbye.
Action: HANGUP
Next States:

---
