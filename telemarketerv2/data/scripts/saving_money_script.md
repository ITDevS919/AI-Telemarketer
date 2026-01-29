# AI Telemarketer Script: Saving Money Focus (v1.3 - Updated Intro Flow)

# STATE: INITIAL_GREETING_SEQUENCE
Action: CUSTOM_LOGIC_INITIAL_GREETING
Dialogue_with_name: Hi can I speak to {{owner_first_name}} please?
Dialogue_no_name: Hi can I speak to the owner please?
Next States: AWAIT_INITIAL_RESPONSE

---

# STATE: AWAIT_INITIAL_RESPONSE
# Action: LISTEN
Next States: OWNER_ON_PHONE_REINTRODUCE, EXPLAIN_CALL_INTRODUCTORY, PITCH_INTEREST_TO_GATEKEEPER, AWAIT_OWNER_AVAILABILITY_RESPONSE, HANGUP_SM
# e.g., User: "Yes, speaking" / "Yes, I am the owner" -> OWNER_ON_PHONE_REINTRODUCE
# e.g., User: "What's it regarding?" -> EXPLAIN_CALL_INTRODUCTORY
# e.g., User: "I'll get them" -> CONFIRM_OWNER_COMING_TO_PHONE
# e.g., User: "They're not here" -> PITCH_INTEREST_TO_GATEKEEPER

---

# STATE: EXPLAIN_CALL_INTRODUCTORY
Dialogue: Oh, it's nothing serious, it's just a quick introductory call. My name is Isaac from Pro Active. Is the owner there?
Action: LISTEN
Next States: AWAIT_OWNER_AVAILABILITY_RESPONSE

---

# STATE: AWAIT_OWNER_AVAILABILITY_RESPONSE
# Action: LISTEN
Next States: CONFIRM_OWNER_COMING_TO_PHONE, OWNER_ON_PHONE_REINTRODUCE, PITCH_INTEREST_TO_GATEKEEPER, HANGUP_SM
# e.g., User: "I'll get them" -> CONFIRM_OWNER_COMING_TO_PHONE
# e.g., User: "They're not here" / "Can I take a message?" -> PITCH_INTEREST_TO_GATEKEEPER
# e.g., Owner comes to phone -> OWNER_ON_PHONE_REINTRODUCE

---

# STATE: PITCH_INTEREST_TO_GATEKEEPER
Dialogue: We're a well-established UK company called Proactiv. We work closely with {{ business_category | default: 'independent businesses' }}. We've got some great ways to show you how to reduce overheads, and at the same time, we've got some great ways to show you how to increase profits for free. But yeah, just need to run it by the owner if they're around today.
Action: LISTEN
Next States: AWAIT_GATEKEEPER_DECISION_AFTER_PITCH

---

# STATE: AWAIT_GATEKEEPER_DECISION_AFTER_PITCH
# Action: LISTEN
Next States: SCHEDULE_CALLBACK_SM, HANGUP_SM, CONFIRM_OWNER_COMING_TO_PHONE

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
Dialogue: Our Managing Director has over 30 years' experience supporting independent businesses like yours. He's developed several unique concepts that both increase customer base and reduce overheads. His most recent invention helps bring in more customers through word-of-mouth, for FREE. He found and addressed the main reasons why only a small percentage of people act on word-of-mouth recommendations and why that figure has been dropping. The results for businesses like yours have been spectacular. It's a real game-changer. Sounds pretty interesting, doesn't it?
Action: LISTEN
Next States: AWAIT_POST_INTEREST_PITCH_RESPONSE

---

# STATE: AWAIT_POST_INTEREST_PITCH_RESPONSE
# Action: LISTEN
# Next states here should lead towards SM focus or MM switch
Next States: SCRIPT_SELECTION_SM, PITCH_APPOINTMENT_SM, HANDLE_OBJECTION_SM, NOT_INTERESTED_SM, REDIRECT_TO_MAKING_MONEY

---

# STATE: SCRIPT_SELECTION_SM
Dialogue: What's more important for your business right now - reducing your expenses or bringing in more customers?
Action: LISTEN
# If they choose saving -> INTRO_RESPONSE_SM (or PRE_CLOSE_SAVING_SM?)
# If they choose making -> REDIRECT_TO_MAKING_MONEY
Next States: INTRO_RESPONSE_SM, REDIRECT_TO_MAKING_MONEY, HANDLE_OBJECTION_SM, CLARIFICATION_SM, NOT_INTERESTED_SM

---

# STATE: REDIRECT_TO_MAKING_MONEY
Dialogue: It sounds like bringing in more customers is a priority for you. Our Managing Director has actually developed several unique approaches that increase your customer base through word-of-mouth marketing, completely FREE. Would it be helpful if I focused more on those solutions?
Action: LISTEN
Next States: SWITCH_TO_MAKING_SCRIPT, INTRO_RESPONSE_SM, HANDLE_OBJECTION_SM, NOT_INTERESTED_SM

---

# STATE: SWITCH_TO_MAKING_SCRIPT
Dialogue: Great, let me tell you about our customer acquisition solutions instead.
Action: SWITCH_SCRIPT
Target Script: making_money_script.md
Target State: INTRO_RESPONSE_MM # Maybe PITCH_APPOINTMENT_MM if interest is high?

---

# --- End of New/Modified Intro Flow ---

# --- Original SM States (Need review for integration points) ---

# STATE: START_SM # DEPRECATED by INITIAL_GREETING_SEQUENCE
# Action: CUSTOM_LOGIC_INITIAL_GREETING
# Dialogue_with_name: Hi can I speak to {{owner_first_name}} please?
# Dialogue_no_name: Hi can I speak to the owner please?
# Next States: GREETING_RESPONSE_SM, INTRO_PROACTIV_SM, GATEKEEPER_DETECTED_SM, CALLBACK_REQUESTED_SM, DECLINE_SM

# ---

# STATE: GREETING_RESPONSE_SM # DEPRECATED by new intro flow
# Dialogue: I'm calling regarding some concepts we've developed to improve cashflow and reduce overheads for businesses. I need to speak with the business owner. Is that you?
# Action: LISTEN
# Next States: INTRO_PROACTIV_SM, GATEKEEPER_DETECTED_SM, CALLBACK_REQUESTED_SM, DECLINE_SM

# ---

# STATE: GATEKEEPER_DETECTED_SM # DEPRECATED by new intro flow (PITCH_INTEREST_TO_GATEKEEPER)
# Dialogue: Okay, thank you. Could you let the owner know Isaac from Proactiv called regarding some concepts developed to improve cashflow and reduce overheads? When would be a good time for me to call back to speak with them directly?
# Action: LISTEN
# Next States: SCHEDULE_CALLBACK_SM, HANGUP_SM

# ---

# STATE: INTRO_PROACTIV_SM
# This state is potentially entered after SCRIPT_SELECTION_SM or SWITCH_TO_SAVING_SCRIPT
# The dialogue should assume interest in saving money has been established.
Dialogue: Excellent. Focusing on improving cashflow and reducing overheads then. Our Managing Director has developed several powerful concepts in this area. {{ business_category | default: '' }}
Action: TALK
Next States: INTRO_RESPONSE_SM # Or maybe BUSINESS_DISCOVERY_SM or PRE_CLOSE_SAVING_SM?

---

# STATE: INTRO_RESPONSE_SM
# Dialogue: Which aspects of reducing costs or improving cashflow would be most valuable to your business right now?
# This feels redundant if they already chose SM focus in SCRIPT_SELECTION_SM. Maybe go direct?
# Let's refine this state. Perhaps ask about specific cost areas?
Dialogue: Okay, regarding cost reduction, are there any specific areas like supplier costs, energy, or operational efficiency that are particularly on your mind?
Action: LISTEN
Next States: BUSINESS_DISCOVERY_SM, PRE_CLOSE_SAVING_SM, HANDLE_OBJECTION_SM, CLARIFICATION_SM, NOT_INTERESTED_SM

---
# ... Rest of the SM script states follow ...
# (Ensure states like BUSINESS_DISCOVERY_SM, BUSINESS_RESPONSE_SM, PRE_CLOSE_SAVING_SM etc. make sense in this flow)

# STATE: BUSINESS_DISCOVERY_SM
Dialogue: Before I continue, may I ask what type of business you operate and what your biggest priorities are right now? This will help me provide more relevant examples of how we've helped similar businesses with their specific needs.
Action: LISTEN
Next States: BUSINESS_RESPONSE_SM, REDIRECT_TO_MAKING_MONEY, CLARIFICATION_SM, NOT_INTERESTED_SM

---

# STATE: BUSINESS_RESPONSE_SM
Dialogue: Thank you for sharing that. In your industry specifically, we've helped similar businesses reduce their operational costs by 15-20% on average. This typically translates to thousands in savings annually that go straight to your bottom line. Would you like to know more about how we could achieve similar results for your business?
Action: LISTEN
Next States: PRE_CLOSE_SAVING_SM, HANDLE_OBJECTION_SM, CLARIFICATION_SM, NOT_INTERESTED_SM

---

# STATE: CLARIFICATION_SM
Dialogue: I understand you'd like more information. Our service specifically helps businesses like yours reduce costs and improve cashflow without disrupting your operations. We've developed several approaches that identify inefficiencies in common business expenses, supply chain, and resource allocation. Would you like to hear how this could work for your specific business?
Action: TALK
Next States: CLARIFICATION_RESPONSE_SM

---

# STATE: CLARIFICATION_RESPONSE_SM
Dialogue: Is that a bit clearer? I'd be happy to explain more about how this might benefit your specific business.
Action: LISTEN
Next States: PRE_CLOSE_SAVING_SM, HANDLE_OBJECTION_SM, NOT_INTERESTED_SM

---

# STATE: PRE_CLOSE_SAVING_SM
Dialogue: Saving money for a business is effectively as good as generating new revenue, I'm sure you would agree?
Action: TALK
Next States: PITCH_APPOINTMENT_SM

---

# STATE: PITCH_APPOINTMENT_SM
Dialogue: Fantastic. The best way to see how this could work specifically for your business is with a quick ten to fifteen minute remote demonstration. We can show you the concept and discuss the potential impact. Would you be open to scheduling that sometime this week or next?
Action: LISTEN
Next States: BOOK_APPOINTMENT_SM, HANDLE_OBJECTION_SM, PITCH_WAMAILER_SM, NOT_INTERESTED_SM

---

# STATE: HANDLE_OBJECTION_SM
Dialogue: I understand. Reducing overheads might seem complex, but often there are straightforward savings to be found. Our chat is just 10-15 minutes to identify if there's potential for your business. Could we find a brief slot next week perhaps?
Action: LISTEN
Next States: BOOK_APPOINTMENT_SM, HANDLE_OBJECTION_BUSY_NOW_SM, HANDLE_OBJECTION_BUSY_BUSINESS_SM, HANDLE_OBJECTION_BUSY_APPOINTMENT_SM, HANDLE_OBJECTION_NI_SM, PITCH_WAMAILER_SM

---

# STATE: HANDLE_OBJECTION_NI_SM
Dialogue: Okay, I understand reducing overheads might not be a top focus right now. Just to confirm, exploring potential savings isn't something you're interested in at the moment?
Action: LISTEN
Next States: PITCH_APPOINTMENT_SM, PITCH_WAMAILER_SM, HANGUP_NI_SM

---

# STATE: HANDLE_OBJECTION_BUSY_NOW_SM
Dialogue: I appreciate you're busy running your business, and I've called unexpectedly. I also know you need more information. The way we approach this is a brief 10-15 minute remote chat to pinpoint potential savings. Could we schedule that for a more convenient time, maybe later today or tomorrow?
Action: LISTEN
Next States: BOOK_APPOINTMENT_SM, PITCH_WAMAILER_SM, NOT_INTERESTED_SM

---

# STATE: HANDLE_OBJECTION_BUSY_BUSINESS_SM
Dialogue: That's great to hear business is keeping you busy! Even when busy, ensuring overheads are optimised helps maximize profitability. Our chat is very quick, just 10-15 minutes remotely, to see if we can identify potential savings without taking much of your time. Would that be feasible?
Action: LISTEN
Next States: BOOK_APPOINTMENT_SM, PITCH_WAMAILER_SM, NOT_INTERESTED_SM

---

# STATE: HANDLE_OBJECTION_BUSY_APPOINTMENT_SM
Dialogue: I understand you run a busy business. We work mainly with independent owners, so our chats are designed for efficiency. They're only 10-15 minutes and done remotely via video call, offering flexibility. We can usually find a time between 8 am and 8:30 pm, even evenings or weekends if needed.
Action: TALK
Next States: PRE_CLOSE_APPOINTMENT_SM

---

# STATE: PRE_CLOSE_APPOINTMENT_SM
Dialogue: I am sure it's worth finding just 15 minutes to potentially uncover ways to reduce your business overheads? What time might work for that brief chat?
Action: LISTEN
Next States: BOOK_APPOINTMENT_SM, PITCH_WAMAILER_SM, NOT_INTERESTED_SM

---

# STATE: BOOK_APPOINTMENT_SM
Dialogue: Fantastic! What day and time works best for you for that quick 10-15 minute remote chat?
Action: LISTEN
Next States: CONFIRM_APPOINTMENT_SM, CALLBACK_REQUESTED_SM, PITCH_WAMAILER_SM

---

# STATE: CONFIRM_APPOINTMENT_SM
Dialogue: Okay, excellent. I have scheduled our chat for [Appointment Day] at [Appointment Time]. I'll send a calendar invitation with the link shortly. Thank you for your time, and have a great day! Goodbye.
Action: HANGUP
Next States:

---

# STATE: PITCH_WAMAILER_SM
Dialogue: Okay, I understand if scheduling a chat right now is difficult. We have prepared an information pack outlining some common areas for savings. Would you like me to send that over to your mobile via WhatsApp?
Action: LISTEN
Next States: GET_WAMAILER_DETAILS_SM, PITCH_EMAILER_SM, NOT_INTERESTED_SM

---

# STATE: GET_WAMAILER_DETAILS_SM
Dialogue: Great. Can I confirm the best mobile number to send the WhatsApp info pack to? [Listen and confirm number]. Okay, I'll send that across shortly. It also includes details on some fantastic introductory offers we run annually – we offer 50 businesses in each county a massive discount for helping us create awareness through their positive results. These offers often include discounts up to 50% and tend to get claimed within 24-48 hours. There's contact info in the pack if you're interested after reviewing it.
Action: LISTEN
Next States: CONFIRM_WAMAILER_SM

---

# STATE: CONFIRM_WAMAILER_SM
Dialogue: Perfect, I've made a note to send that WhatsApp pack over to [Confirmed Mobile Number]. Thanks again for your time today. Goodbye.
Action: HANGUP
Next States:

---

# STATE: PITCH_EMAILER_SM
Dialogue: No problem at all. As an alternative, I could email that information pack over to you if you prefer?
Action: LISTEN
Next States: GET_EMAIL_DETAILS_SM, NOT_INTERESTED_SM, HANGUP_SM

---

# STATE: GET_EMAIL_DETAILS_SM
Dialogue: Sure thing. What's the best email address to send the information pack and offer details to? [Listen and confirm email].
Action: LISTEN
Next States: CONFIRM_EMAILER_SM

---

# STATE: CONFIRM_EMAILER_SM
Dialogue: Excellent, I have that down as [Confirmed Email Address]. I'll email the pack across shortly. Thank you for your time. Goodbye.
Action: HANGUP
Next States:

---

# STATE: CALLBACK_REQUESTED_SM
Dialogue: Of course. When would be a better time for me to reach you?
Action: LISTEN
Next States: SCHEDULE_CALLBACK_SM, NOT_INTERESTED_SM

---

# STATE: SCHEDULE_CALLBACK_SM
Dialogue: Okay, could you give me a specific day and time that works best?
Action: LISTEN
Next States: CONFIRM_CALLBACK_SM, NOT_INTERESTED_SM

---

# STATE: CONFIRM_CALLBACK_SM
Dialogue: Got it. I will call you back on [Callback Day] around [Callback Time]. Thank you. Goodbye.
Action: HANGUP
Next States:

---

# STATE: DECLINE_SM
Dialogue: Okay, no problem. Thanks for letting me know. Have a good day. Goodbye.
Action: HANGUP
Next States:

---

# STATE: NOT_INTERESTED_SM
Dialogue: Okay, I understand this isn't the right time or fit. Thank you for your time today. Have a great day. Goodbye.
Action: HANGUP
Next States:

---

# STATE: HANGUP_NI_SM
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
# See notes in making_money_script.md for this state.
Next States: HANDLE_OBJECTION_SM, SCRIPT_SELECTION_SM, NOT_INTERESTED_SM, HANGUP_SM

---

# STATE: HANGUP_SM
Dialogue: Okay, thank you for your time. Goodbye.
Action: HANGUP
Next States:

---

# STATE: ERROR_STATE_SM
Dialogue: Apologies, I seem to be having some technical issues. I'll need to end the call now. Goodbye.
Action: HANGUP
Next States:

--- 