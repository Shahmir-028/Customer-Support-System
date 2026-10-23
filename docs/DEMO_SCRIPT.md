# Demo script and viva preparation

Total time: about 10 minutes. The words of the AI replies change a little from run to run. The **route, tools, cards, tickets and emails** are what you should point at, because they come from code.

## A. Before the demo (checklist)

1. PostgreSQL is running. Backend (`uvicorn ...`) and frontend (`npm run dev`) are running in two terminals.
2. `.env` is filled: `GOOGLE_API_KEY`, `LLM_MODEL`, `SMTP_*`, `SUPPORT_TEAM_EMAIL`, `ADMIN_PASSWORD`, `STRIPE_SECRET_KEY`.
3. The customers you will use have **real inbox addresses** (Ali = id 1, Sara = id 2):
   ```sql
   UPDATE customers SET email = 'inbox1@gmail.com' WHERE id = 1;
   UPDATE customers SET email = 'inbox2@gmail.com' WHERE id = 2;
   ```
4. Reset the demo data (run in psql after `\c support`):
   ```sql
   UPDATE orders SET refunded = false, refund_reference = NULL, status = 'delivered' WHERE id IN (1002, 1004);
   UPDATE orders SET shipping_address = 'Gulshan, Karachi' WHERE id = 1003;
   DELETE FROM tickets;      -- optional: start with an empty ticket list
   ```
5. Open these tabs in the browser: the chat (`localhost:5173`), the admin page (`localhost:5173/#admin`), your inbox, and the Stripe dashboard in **Test mode** (Payments / Refunds).
6. Do one test message before the audience arrives, so the embedding model and the AI service are warm.
7. Keep the architecture picture (`docs/architecture.png`) on the first slide.

## B. The demo, scenario by scenario

| # | You type | What you should see | What to say |
|---|---|---|---|
| 1 | `Refund policy kya hai?` | Indicator "Searching knowledge base...", then an answer based on the refund policy (7 days, 200 USD limit). No card. | "Knowledge Agent. It answers only from our documents (RAG), so it does not invent policies." |
| 2 | `Mera order 1001 kahan hai?` | Indicator "Checking your order...", an **order card** (Wireless Earbuds, shipped, ETA 2 days). | "The Router sent this to the Action Agent, which called `get_order_status` on PostgreSQL." |
| 3 | `Order 1002 ka refund chahiye` | **Refund card** (12 USD with a Stripe reference `re_...`) and an **email card**. Reply says the refund is done and a confirmation email was sent. Ask `Mera order 1002 kahan hai?` afterwards: the order card now shows the status **refunded**. | "Action Agent refunded through Stripe. Then **code** (not the LLM) saw the success and passed the case to the Email Agent." Show the Stripe dashboard (payment + refund) and the email in the inbox. |
| 4 | `Order 1002 ka dobara refund karo` | A polite refusal: already refunded. No new refund card. | "Safety rule in code: one refund per order." |
| 5 | `Order 1001 ka refund karo` | A refusal: the order is shipped and can only be refunded after delivery. | "Only delivered or cancelled orders are refundable. The tool enforces it even if the LLM wanted to refund." |
| 6 | `Order 1003 ka address Clifton, Karachi kar do` | **Update card** (shipping_address) and a confirmation email card. | "Address changes are allowed only while the order is processing." |
| 7 | `Order 1001 ka address badal do` | A refusal (order already shipped). | "Same idea: business rules live in the tools." |
| 8 | `Order 1004 ka refund karo` (250 USD) | Indicator "Escalating...", a yellow **escalation banner with a ticket number**. | "Above 200 USD a human must approve. The tool answers `REFUND_NEEDS_APPROVAL`, code routes to the Escalation Agent, which creates a ticket with the full context." Show the **email the support team received**. |
| 9 | `Mujhe manager se baat karni hai` | The bot asks for your **email address** (no ticket yet). | "With no order number, there is no way to reach the customer, so the tool refuses to create a ticket until we have an email." |
| 10 | Type your email, e.g. `inbox1@gmail.com` | Escalation banner with a new ticket number. | "The conversation memory (LangGraph checkpointer) remembers why we asked." |

## C. Admin part (2 minutes)

1. Open `localhost:5173/#admin`. Show that the normal customer page has **no admin tab**.
2. Log in with `ADMIN_PASSWORD`. Show the ticket list (the red number counts open tickets).
3. Click the ticket from step 8. Read the **summary written by the AI** for the human agent.
4. Set status **Resolved**, write: `Your refund of 250 USD has been approved and will reach your card in 5-7 days.` Keep "Email the customer" ticked and press **Save update**. The green message shows `sent to ...`.
5. Show the email arriving in the customer's inbox. "The customer's reply goes to the support team (Reply-To)."
6. Back in the chat: `Ticket <number> ka status batao, meri email <the email of that ticket>`. A **ticket card** shows "resolved" and the support message.
7. Try the same with a wrong email. The bot only says that no ticket was found. "It never reveals whether the ticket exists."

## D. Extra points to mention (30 seconds each)

- **Memory:** ask `Mera order 1001 kahan hai?` and then `Uski ETA kya hai?`. The assistant answers from the conversation history.
- **Languages:** the agents answer in the customer's style (English, Urdu, Roman Urdu).
- **Resilience:** if the AI service says 503/429, the backend retries by itself and shows "AI service is busy, retrying...".
- **Why not a single agent?** Each agent has a small prompt and only the tools it needs. That makes behaviour easier to test and safer.

## E. Likely viva questions and short answers

1. **What is agentic AI here?** The system decides what to do, calls tools that change real data (refund, update, email, ticket), and loops until the task is done or hands over to a human.
2. **Why multi-agent instead of one agent with all tools?** Smaller prompts, fewer tools per agent (less confusion), clear responsibilities, and routing rules in code. It is also easier to test one agent at a time.
3. **Why LangGraph?** It gives a graph with conditional edges, shared state, memory per conversation, and a clean way to decide the next step from tool results.
4. **Where does LangChain fit?** It supplies the building blocks: model wrapper, `@tool` functions, document splitter, retriever, vector store wrapper. LangGraph connects these blocks.
5. **What is RAG and why use it?** The model searches our documents first and answers from them, so replies match company policy and do not rely on the model's memory. We use chunks of 500 characters, local MiniLM embeddings and ChromaDB.
6. **Semantic chunking or fixed chunking?** Fixed-size recursive chunking (500 characters, 80 overlap). Retrieval itself is semantic, because chunks are searched by embedding similarity. Our documents are short and already structured, so semantic chunking would add little.
7. **How do you stop the AI from refunding wrongly?** The rules are in the tool code: 200 USD limit, delivered/cancelled only, once per order, never above the order total. The LLM cannot bypass them.
8. **What happens when the AI service is down or limited?** The backend retries up to 3 times and resumes from the last checkpoint; if it still fails the user gets a friendly message.
9. **How is the admin page protected?** Password login with a token, a login rate limit, and every admin endpoint checks the token. Without `ADMIN_PASSWORD` the admin stays disabled.
10. **How does the customer learn that a ticket is resolved?** The admin saves the status with a message and the system emails the customer. The customer can also ask the chat for the status using ticket number and email.
11. **Is the data safe?** Secrets are in `.env`, Stripe is in test mode, other customers' data is never shown, and ticket lookup needs two matching values. Known gaps are listed in the README (unverified email, in-memory sessions).
12. **How would you evaluate it?** Build a list of test messages with the expected route and tool, run them automatically, and measure router accuracy, tool success and wrong-action rate. Also track escalation rate and customer satisfaction.
13. **What would you improve next?** Database-backed memory, email verification, real token streaming, a delivery date check for the 7-day refund window, and live handover to the human agent.

## F. If something goes wrong during the demo

| Problem | Quick fix |
|---|---|
| Message `AI service is busy or its free limit is reached` | Wait a minute and ask again. If it repeats, the daily free quota is used up: switch `LLM_MODEL` in `.env` to another model with a higher daily limit and restart the backend. |
| The first answer is slow | The embedding model is loading. Ask one test question before the demo. |
| No email arrives | Check spam, check `SMTP_EMAIL` and the App Password (no spaces), and read the backend terminal for `Email failed: ...`. |
| Refund says already refunded | Run the reset SQL in section A. |
| Admin shows "Could not load data" | Backend not running, or you restarted it (restarts log everyone out). Log in again. |
| Blank page | Press Ctrl + Shift + R. The page shows the error text if the app crashes; send that text to whoever helps you debug. |
