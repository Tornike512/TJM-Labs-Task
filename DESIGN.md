My planning
TJM Labs sell AI software that does repeated office work for pharmacies and pharmacies call the number on TJM Labs's website and today human must pick up and we want to build an ai agent that answers instead of human
this is how I think agent should work

1. first check the caller's phone number in our api endpoint I was sent which is pharmacy list
2. if that number exists in that list, ai agent greets them with their name and also uses their data of past calls
3. if the number is not in the list, that means the ai agent should ask for the pharmacy name and Rx volume and also explain how TJM Labs help pharmacies with high Rx volume if the rx volume provided is high or directly asked
4. at the end the AI agent should send an email info or book a callback with our sales team
5. agent should say it's an ai agent in the start, it should use simple words and not too complex just in case pharmacy person might not be very good at english
6. the agent should never make up things, if it doesn't know something, it should say something follow up and also ask if the pharmacy caller wants to escalate to human because it can't answer itself, so ai agent should give the caller two choices in this case
7. the language should be English only at start, could use another languge but can't support all the languages because LLM is still not good at all languages yet, we can also add many languages support and AI can automatically detec the language once words are translated to transcript.
8. in case of success, follow-ups booked and zero missed calls


my decisions

1. callers are pharmacy owners or staff and business people and not patients, if patient calls by mistake, the agent says we are software company and points back to their paharmacy, no medical advice ever
2. the agent handles sales calls only, if the customer calles for support or help, the agent should navigate them to the support team instead
3. the pharmacy list api is our only source of truth for known pharmacies now, the data in it can be messy, missing fields or junk records from other users, so the code must skip the bad records instad of completely crashing
4. the api doesn't have ready RX volume number, we compute it by adding the prescription counts
5. i chose 80+ as the high rx volume prescriptions because I took this number from the data and some volumes are 55-100 and i chose somewhere in the middle but we can change this anytime
6. if the caller number is not in the list, the ai agent will treat as a new customer, it asks for the pharmacy name and then quietly re-checks in the list by that name just in case it's known and they are calling from a different number,
7. agent should always say it's an ai agent in the start and it's recording
8. ai agent should never ask or store patient health details, if callers starts sharing, ai agent should politely stop because it's illegal
9. in case agents gets stuck or other caller wants human, during business hours, the ai agent can transfer, otherwise book a call or will call the caller again the next day by human


system design I would go for
this is how one call travels

1. a pharmacy calls, the voice platform like vapi or retell picks up, it hold the phone line, turns the callers speech into text and then sends to LLM, llm answers and then we turn back to voice and we answer the caller with a voice
2. the platform see the caller's numbers and passes it to our backend
3. our code checks the nubmers in database with api, we have to be sure the database is pre-warmed and indexed so the answer is very fast to avoid latency, the api should pass only the important information to the LLM so the generation won't take long, I would turn off thinking mode too for the LLM
4. if the number is not in the list, the agent asks for pharmacy name and then our code will check it in the list by that name
5. during the entire call, one loop generates, ears to brain to mouth and repeat, the caller speaks, words become text, the brain writes reply and mouth speaks it
6. the brain has three tools that can ask the user, follow up email, book a callback or transfer to human, usually at the end of the call
7. after the call the full transcript is saved for improvement in the future
8. for the first version, we rent the voice platform instead of building it from parts like twillio and separate STT and TTS


4 conversation flow
for the voice i would pick friendly adult voice, not too old not too young

1. opening would be sometihng like this, first we should say that this is an ai and call is being recorded in different speech, then we shoul say hi, this is the TJM Labs Ai assistant, is this HealthFirst Pharmacy in new york? if we don't know the caller, just how can I help you today instead of saying specific pharmacy
2. it should explain how TJM Labs helps, like RX volume 80+ get the high-volume pitch, smaller pharmacies get the normal pitch
3. the ai should always answers on questions it knows and should never make things up, if it doesn't know, it should offer follow up or transfer to human, if human is not available, call again the next day in case the caller doesn't have any other question
4. at the end, thanks for calling, have a nice day
5. rules: caller wants human, the ai transfers to them if human is available if not book a call, if caller starts sharing patient details, politely stop them, if patient calls by a mistake, say that we are software company and to call the pharmacy directly with polite text, if it's a support question, transfer to support team, if caller seems confused twice in a row, transfer to human


how the brain works

1. we should use fast model that is not too pricy like sonnet 5, we should try many models and find the cheapest alternative with same output, we shouldn't use thinking mode because of latency
2. the LLM should never email the caller or book a call, it should call already built python code and that code should do the job, llm should just pass the parameters


edge cases

1. what if pharmacy list api is down or slow? the agent doesn't crash or stall, it continues if the callr is unknown, collets info by asking and follow-ups still work
2. in rare cases the voice platform or LLM fails mid-call, with short apology the agent and callback the agent should hang up an re-call to them, also we should log the failure to know why it happened and if it was on our side and not LLM like claude
3. if there is a noise and our agent can't hear, it should ask for a callback and say it's hard to hear
4. if caller interrupts while the robot talks, the robot should stop and listen, the voice platforms suport this too
5. we can decide if it's only english or not, if it's more languages than that, LLM can detect it and answer accordingly
6. if it's prank or someone calls and just doesn't hang up like they are competitors or something and wants us to waste money on LLMs, if there are no voices or words or valid questions for 1-2 minutes, we hang up but very hard to avoid this, they can recall and we can block that user if the same issue occurs multiple times, but very rare case
7. if two pharmacies are calling with the same name in the list, confirm by the city
8.


testing

1. to test we can fake calls in texts, we play the caller ourselves and run the normal routes, pharmacy both unknow and known and each too, everything there is
2. we should trap the questions, we can ask questions like, how much does it cost per month? price is banned and we should offer follow up, are you Hipaa certified? this is a legal claim and should never improvise legal claim, you are better than our competitor and say the name, the ai agent shouldn't brag
3. on purpose unplug the pharmacy api, kill the LLM mid call, stay silent, interrupt mid-sentence, the ai agent should react as described above
4. all these test conversations saved as one fixed exam, before any change goes live, new fact or new prompt wording, we should run the who exam and compare answers, this is regression testing so we are sure ai-agent doesn't get worse
5. after launch read transcripts weekly, we can use other llms for reading them since they are much better than humans in this, we should also look at follow-ups booked per call, missed calls should be zero, how often the robot needed human and the escalation rate, how often it recognized callers correctly