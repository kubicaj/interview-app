import asyncio
import threading
import functools
import gradio as gr

from src.interview_config import InterviewConfig
from src.interview_app import InterviewApp

POSITIONS = list(InterviewConfig.get_active_instance().all_open_positions.values())

PRIMARY_COLOR = "#224488"
BG = "#f4f4fb"
MAX_COLUMNS = 4


def load_position_detail(position_index):
    """
    Load and show the detailed content of a selected job position.

    Args:
      position_index (int) - Index of the selected position in the POSITIONS list

    Return:
      (tuple) - Visibility update for the UI, position content markdown, and position title
    """
    open_position = POSITIONS[position_index]
    return gr.update(visible=True), open_position.open_position_content, open_position.position_title


def hide_detail():
    """
    Hide the job position detail section.

    Args:
      None

    Return:
      (tuple) - UI update to hide detail section and clear its content
    """
    return gr.update(visible=False), "", ""


def set_interview_buttons(disable=True):
    """
    Enable or disable all interview buttons.

    Args:
      disable (bool) - Whether to disable the buttons (default: True)

    Return:
      (list) - List of Gradio update objects controlling button interactivity
    """
    return [gr.update(interactive=(not disable)) for _ in POSITIONS]


def start_interview(position_index: int, cv_content: str):
    """
    Start the interview process for a selected job.

    Args:
      position_index (int) - Index of the job position
      cv_content (str) - Text content extracted from the uploaded CV

    Return:
      (tuple) - Updates to show interview UI, selected position metadata, button states, initial chat message, and interview app state
    """
    initial_message = (
        f"Hi. You are here because you apply for position {POSITIONS[position_index].position_title}. Can we start please?"
    )
    interview_app = InterviewApp(POSITIONS[position_index].position_identifier, cv_content)
    interview_app.create_graph()
    return (
        gr.update(visible=True),
        POSITIONS[position_index].position_title,
        position_index,
        *set_interview_buttons(disable=True),
        [{"role": "assistant", "content": initial_message}],
        [{"role": "assistant", "content": initial_message}],
        interview_app
    )


def show_confirm_modal():
    """
    Display the confirmation modal before ending the interview.

    Args:
      None

    Return:
      (Gradio Update) - Update to show confirmation modal
    """
    return gr.update(visible=True)


def hide_confirm_modal():
    """
    Hide the confirmation modal.

    Args:
      None

    Return:
      (Gradio Update) - Update to hide confirmation modal
    """
    return gr.update(visible=False)


async def end_interview_app(interview_app: InterviewApp, history: list[dict]):
    """
    Asynchronously send a final message to the interview graph to end the conversation.

    Args:
      interview_app (InterviewApp) - Active interview app instance
      history (list[dict]) - Chat history log

    Return:
      None
    """
    interview_app.invoke_user_query("Finish the interview now", history)


def end_interview(interview_app: InterviewApp, history: list[dict]):
    """
    End the interview session and reset related UI states.

    Args:
      interview_app (InterviewApp) - Active interview app instance
      history (list[dict]) - Chat history log

    Return:
      (tuple) - UI updates to hide interview section, reset state and re-enable interview buttons
    """

    def async_wrapper():
        asyncio.run(end_interview_app(interview_app, history))

    threading.Thread(target=async_wrapper).start()

    return (
        gr.update(visible=False),
        "",
        -1,
        *set_interview_buttons(disable=False),
        gr.update(visible=False),
    )


def chat_function(user_input, history: list[dict], interview_app: InterviewApp):
    """
    Handle user input during the chat, process it through the interview app, and update history.

    Args:
      user_input (str) - User's message
      history (list[dict]) - Chat history
      interview_app (InterviewApp) - Current interview app instance

    Return:
      (tuple) - Updated chat history for chatbot and UI
    """
    try:
        result = interview_app.invoke_user_query(user_input, history)
    except Exception as ex:
        interview_app.logger.exception(ex)
        result = {"role": "assistant", "content": "Unexpected issue happen. Please try to answer again"}
    history = history + [{"role": "user", "content": user_input}] + [result]
    return history, history, ""


def chunk(seq, size):
    """
    Split a sequence into chunks of specified size.

    Args:
      seq (list) - Sequence to be chunked
      size (int) - Size of each chunk

    Return:
      (generator) - Chunks of the original list
    """
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def handle_cv_upload(file):
    """
    Handle the uploaded CV file and extract content.

    Args:
      file (File) - Uploaded PDF file containing the CV

    Return:
      (tuple) - UI updates and extracted CV content
    """
    if file is None:
        return gr.update(visible=True), gr.update(visible=False), ""
    content_of_cv = InterviewConfig.get_pdf_content(file)
    return gr.update(visible=False), gr.update(
        visible=True), "✅ CV received! You may now browse open positions.", content_of_cv


# ========== UI Layout ==========
with gr.Blocks(css=f"""
.centered-row {{
    display: flex;
    justify-content: center !important;
    flex-wrap: wrap;
}}

.card {{
    background: #ffffff;
    border-radius: 18px;
    box-shadow: 0 4px 20px rgba(34, 68, 136, 0.1);
    border: 1px solid #dce3f3;
    margin: 12px;
    width: 300px;
    height: 320px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
    padding: 24px 18px;
    text-align: center;
    transition: transform 0.2s;
    box-sizing: border-box;
    animation: fadeIn 0.5s ease-in;
}}

.card:hover {{
    transform: translateY(-5px);
    box-shadow: 0 6px 24px rgba(34, 68, 136, 0.18);
}}

.card-title {{
    color: {PRIMARY_COLOR};
    font-size: 1.2em;
    font-weight: 600;
    margin-bottom: 8px;
}}

.card-desc {{
    color: #555;
    font-size: 0.95em;
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    margin-bottom: 12px;
    padding: 0 8px;
}}

#header {{
    text-align: center;
    color: {PRIMARY_COLOR};
    margin-bottom: 30px;
}}

#interview-title {{
    margin-top: 20px;
    font-size: 1.3em;
    font-weight: 600;
    color: #333;
}}

#interview-section {{
    background: #f9faff;
    border: 1px solid #dce6f9;
    border-radius: 16px;
    padding: 20px;
    margin-top: 30px;
}}

@keyframes fadeIn {{
    0% {{ opacity: 0; transform: translateY(10px); }}
    100% {{ opacity: 1; transform: translateY(0); }}
}}
""") as demo:
    # ===== Header =====
    gr.Markdown(
        """
        # 🚀 Join Our Team!
        Upload your CV to discover exciting career opportunities tailored for you.

        1. 📎 **Upload your CV** using the button above.  
        2. 🧭 **Explore open positions** that match your profile.  
        3. 🔍 **Click "Show detail"** to learn more about a specific role.  
        4. 🤖 **Start an AI interview** for your chosen position.  
        5. 📝 **Chat with the AI interviewer** and get real-time feedback.  
        6. ✅ **End the interview** to explore other roles or update your CV.
        """,
        elem_id="header"
    )

    # ===== CV Upload Section =====
    with gr.Row():
        uploaded_file = gr.File(label="Upload your CV (PDF)", file_types=[".pdf"])
        upload_button = gr.Button("Submit CV", variant="primary")

    upload_feedback = gr.Markdown("", visible=False)
    cv_warning = gr.Markdown("📎 Please upload your CV to continue.", visible=False)

    # ===== Hidden Job Cards Until CV Uploaded =====
    with gr.Group(visible=False, elem_id="job-cards") as job_card_section:
        show_btns = []
        interview_btns = []
        for chunk_positions in chunk(POSITIONS, MAX_COLUMNS):
            with gr.Row(elem_classes="centered-row"):
                for pos in chunk_positions:
                    with gr.Group(elem_classes="card"):
                        gr.Markdown(f"<div class='card-title'>{pos.position_title}</div>")
                        gr.Markdown(f"<div class='card-desc'>{pos.position_short_summary}</div>")
                        btn_det = gr.Button("Show detail")
                        btn_int = gr.Button("Start interview", variant="primary")
                        show_btns.append(btn_det)
                        interview_btns.append(btn_int)

    # ===== Modal: Position Detail =====
    with gr.Group(visible=False) as detail_group:
        detail_title = gr.Markdown("**Position Detail**", elem_id="modal-title")
        detail_md = gr.Markdown("", elem_id="modal-md")
        btn_close = gr.Button("Close detail", variant="stop")
    btn_close.click(hide_detail, outputs=[detail_group, detail_md, detail_title])

    # ====== App State ======
    interview_chat = gr.Column(visible=False, elem_id="interview-section")
    chosen_position_name = gr.State("")
    interview_application = gr.State(None)
    chosen_position_index = gr.State(-1)
    cv_content = gr.State("")

    # ====== Interview UI ======
    with interview_chat:
        pos_label = gr.Markdown("", elem_id="interview-title")
        chatbot = gr.Chatbot(type="messages")
        state = gr.State([])
        msg = gr.Textbox(label="", placeholder="Type your response here...", lines=4)
        send_btn = gr.Button("Send", variant="primary")
        btn_end = gr.Button("End interview - choose another position", variant="stop")

        send_btn.click(chat_function, [msg, state, interview_application], [chatbot, state, msg])


        def update_title(pos_name):
            return f"### Interview chat for **{pos_name}** position"


        chosen_position_name.change(update_title, chosen_position_name, pos_label)

    # ===== Wire CV Upload Logic =====
    upload_button.click(
        handle_cv_upload,
        inputs=[uploaded_file],
        outputs=[cv_warning, job_card_section, upload_feedback, cv_content]
    )

    # ===== Hook Buttons =====
    for position_index, btn in enumerate(show_btns):
        btn.click(functools.partial(load_position_detail, position_index),
                  outputs=[detail_group, detail_md, detail_title])

    for position_index, btn in enumerate(interview_btns):
        btn.click(
            functools.partial(start_interview, position_index),
            inputs=[cv_content],
            outputs=[interview_chat, chosen_position_name, chosen_position_index] + interview_btns + [chatbot, state,
                                                                                                      interview_application]
        )

    # ===== Confirm End Interview Modal =====
    with gr.Group(visible=False) as confirm_modal:
        confirm_msg = gr.Markdown("Are you sure you want to end the interview?")
        btn_yes = gr.Button("Yes, end interview", variant="stop", scale=0)
        btn_no = gr.Button("No, continue", scale=0)

    btn_end.click(show_confirm_modal, outputs=[confirm_modal])
    btn_no.click(hide_confirm_modal, outputs=[confirm_modal])
    btn_yes.click(
        end_interview,
        inputs=[interview_application, state],
        outputs=[interview_chat, chosen_position_name, chosen_position_index] + interview_btns + [confirm_modal]
    )

# ========== RUN ==========
demo.launch()
