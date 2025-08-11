import functools
import tempfile
import gradio as gr

from src.ui.ui_interview_app import POSITIONS, hide_position_detail, chat_function, handle_cv_upload, \
    load_position_detail, start_interview, show_confirm_modal, hide_confirm_modal, end_interview_with_summary, chunk, \
    create_interview_preparation_sheet

PRIMARY_COLOR = "#224488"
BG = "#f4f4fb"
MAX_COLUMNS = 3

with gr.Blocks(css=f"""
.centered-row {{
    display: flex;
    justify-content: center !important;
    flex-wrap: wrap;
}}
.card {{
    background: #ffffff;
    border-radius: 5px;
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
#card_button {{
    width: auto !important;
    display: inline-block !important;
    min-width: 140px;
    padding: 0.4em 1.2em;
    font-size: 16px;
    font-weight: 600;
    border-radius: 22px;
    background: #1976d2;
    color: #fff;
    border: none;
    margin: 0.2em 0.3em 0.2em 0;
    box-shadow: 0 2px 4px rgba(25,118,210,0.08);
    transition: background .2s;
    text-align: center;
    vertical-align: middle;
}}
#card_button:hover {{
    background: #125ba1;
    color: #ffc;
}}
.button-row {{
    display: flex;
    gap: 0.5em;
    flex-wrap: wrap;
    justify-content: flex-start;
}}
@keyframes fadeIn {{
    0% {{ opacity: 0; transform: translateY(10px); }}
    100% {{ opacity: 1; transform: translateY(0); }}
}}
""") as demo:
    gr.Markdown(
        """# 🚀 Join Our Team or Manage Interviews!
        Welcome to the Interview Assistant. This app is designed **both for candidates looking to join our team** and **for interview managers who need to quickly generate structured interview preparation materials**.

        ## For Candidates
        1. 📎 **Upload a candidate's CV** using the upload button.
        2. 🧭 **Browse open positions** tailored to the CV content.
        3. 🔍 **Show role details** by clicking "Show detail".
        4. 🗣️ **Start an AI-powered interview** for your chosen position.
        5. 📝 **Chat with the AI interviewer** and receive instant feedback.
        6. ✅ **End the interview** to review a summary or try another position.

        ## For Interview Managers
        - 📝 **Create Interview Preparation Sheets**: Choose any open position and quickly generate a detailed interview prep guide. You can optionally add specific HR instructions to the prep sheet.
        - 📥 **Download generated materials** for use in interviews or training.

        ---

        *Use this tool for both interactive AI interviews and to assist with your interview process workflow.*

        """,
        elem_id="header"
    )

    with gr.Row():
        uploaded_file = gr.File(label="📎Upload candidate CV (PDF)", file_types=[".pdf"])
        upload_button = gr.Button("📤 Submit CV", variant="primary")

    upload_feedback = gr.Markdown("", visible=False)
    cv_warning = gr.Markdown("📎 Please upload candidate CV to continue.", visible=False)

    with gr.Group(visible=False, elem_id="job-cards") as job_card_section:
        show_btns = []
        interview_btns = []
        create_preparation_sheet_btns = []
        for chunk_positions in chunk(POSITIONS, MAX_COLUMNS):
            with gr.Row(elem_classes="centered-row"):
                for pos in chunk_positions:
                    with gr.Group(elem_classes="card"):
                        gr.Markdown(f"<div class='card-title'>{pos.position_title}</div>")
                        gr.Markdown(f"<div class='card-desc'>{pos.position_short_summary}</div>")
                        btn_show_detail = gr.Button("🔎 Show detail", elem_id="card_button")
                        btn_start_interview = gr.Button("🗣️ Start interview", elem_id="card_button")
                        btn_create_preparation_sheet = gr.Button("📝 Create preparation sheet", elem_id="card_button")
                        show_btns.append(btn_show_detail)
                        interview_btns.append(btn_start_interview)
                        create_preparation_sheet_btns.append(btn_create_preparation_sheet)

    with gr.Group(visible=False) as detail_group:
        detail_title = gr.Markdown("**Position Detail**", elem_id="modal-title")
        detail_md = gr.Markdown("", elem_id="modal-md")
        btn_close = gr.Button("Close detail", variant="stop")
    btn_close.click(hide_position_detail, outputs=[detail_group, detail_md, detail_title])

    interview_chat = gr.Column(visible=False, elem_id="interview-section")
    chosen_position_name = gr.State("")
    interview_application = gr.State(None)
    chosen_position_index = gr.State(-1)
    cv_content = gr.State("")

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

    upload_button.click(
        handle_cv_upload,
        inputs=[uploaded_file],
        outputs=[cv_warning, job_card_section, upload_feedback, cv_content]
    )

    for position_index, btn in enumerate(show_btns):
        btn.click(functools.partial(load_position_detail, position_index),
                  outputs=[detail_group, detail_md, detail_title])

    for position_index, btn in enumerate(interview_btns):
        btn.click(
            functools.partial(start_interview, position_index),
            inputs=[cv_content],
            outputs=[interview_chat, chosen_position_name, chosen_position_index] +
                    interview_btns + [chatbot, state, interview_application]
        )

    # Preparation sheet modals & workflow
    with gr.Group(visible=False) as prep_sheet_modal:
        prep_sheet_instructions = gr.Textbox(
            label="Additional HR instructions for interview",
            placeholder="Add extra HR interview instructions if required...",
            lines=4
        )
        with gr.Row():
            prep_sheet_confirm = gr.Button("Confirm", variant="primary")
            prep_sheet_cancel = gr.Button("Cancel", variant="secondary")
        prep_sheet_status = gr.Markdown("", visible=False)

    with gr.Group(visible=False) as prep_sheet_progress_modal:
        gr.Markdown("⏳ Generating your preparation sheet. It can take more than 1 minute, please wait ...")

    with gr.Group(visible=False) as prep_sheet_result_group:
        gr.Markdown("📝 Interview Preparation Sheet generated below: (save as .txt)")
        prep_sheet_result = gr.Markdown(label="Preparation Sheet", visible=False)
        prep_sheet_download_btn = gr.File(label="Download Preparation Sheet (TXT)", interactive=False)
        prep_sheet_close_btn = gr.Button("Close", variant="secondary")

    prep_sheet_position_index = gr.State(-1)
    prep_sheet_result_text = gr.State("")
    all_action_buttons = show_btns + interview_btns + create_preparation_sheet_btns


    def open_prep_sheet_modal(position_index, *buttons):
        # Return as many outputs as in outputs=
        return (
            gr.update(visible=True),  # show modal
            gr.update(value=""),  # clear HR box
            position_index,  # update index
            *(gr.update(interactive=False) for _ in buttons)
        )


    def close_prep_sheet_modal(*buttons):
        return (gr.update(visible=False),) + tuple(gr.update(interactive=True) for _ in buttons)


    def hide_modals_and_show_progress(*buttons):
        # Hide HR modal, show progress, keep others disabled
        return (gr.update(visible=False), gr.update(visible=True)) + tuple(
            gr.update(interactive=False) for _ in buttons)


    def generate_prep_sheet_and_store(position_index, cv_content_val, additional_hr_details):
        return create_interview_preparation_sheet(
            position_index=position_index,
            cv_content=cv_content_val,
            additional_hr_details=additional_hr_details
        )


    def display_prep_sheet_result(result_txt, *buttons):
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
        tf.write(result_txt)
        tf.close()
        return (gr.update(visible=True), gr.update(value=result_txt, visible=True), gr.update(value=tf.name),
                result_txt) + \
            tuple(gr.update(interactive=True) for _ in buttons)


    def hide_prep_sheet_result_output(*buttons):
        return (gr.update(visible=False), gr.update(value=""), gr.update(value=None), "") + \
            tuple(gr.update(interactive=True) for _ in buttons)


    for position_index, btn in enumerate(create_preparation_sheet_btns):
        btn.click(
            functools.partial(open_prep_sheet_modal, position_index),
            inputs=all_action_buttons,
            outputs=[prep_sheet_modal, prep_sheet_instructions, prep_sheet_position_index] + all_action_buttons
        )

    prep_sheet_cancel.click(
        functools.partial(close_prep_sheet_modal),
        inputs=all_action_buttons,
        outputs=[prep_sheet_modal] + all_action_buttons
    )

    prep_sheet_confirm.click(
        hide_modals_and_show_progress,
        inputs=all_action_buttons,
        outputs=[prep_sheet_modal, prep_sheet_progress_modal] + all_action_buttons
    ).then(
        generate_prep_sheet_and_store,
        inputs=[prep_sheet_position_index, cv_content, prep_sheet_instructions],
        outputs=[prep_sheet_result_text],
        show_progress=True,
        queue=True
    ).then(
        display_prep_sheet_result,
        inputs=[prep_sheet_result_text] + all_action_buttons,
        outputs=[prep_sheet_result_group, prep_sheet_result, prep_sheet_download_btn,
                 prep_sheet_result_text] + all_action_buttons
    ).then(
        lambda: gr.update(visible=False),
        None, [prep_sheet_progress_modal]
    )

    prep_sheet_close_btn.click(
        hide_prep_sheet_result_output,
        inputs=all_action_buttons,
        outputs=[prep_sheet_result_group, prep_sheet_result, prep_sheet_download_btn,
                 prep_sheet_result_text] + all_action_buttons
    )

    # Interview end summary modal etc
    with gr.Group(visible=False) as confirm_modal:
        confirm_msg = gr.Markdown("Are you sure you want to end the interview?")
        btn_yes = gr.Button("Yes, end interview", variant="stop", scale=0)
        btn_no = gr.Button("No, continue", scale=0)

    btn_end.click(show_confirm_modal, outputs=[confirm_modal])
    btn_no.click(hide_confirm_modal, outputs=[confirm_modal])

    with gr.Group(visible=False) as progress_modal:
        gr.Markdown("⏳ Generating your interview summary. It can take more than 30 seconds. Please wait...")

    with gr.Group(visible=False) as summary_display_group:
        gr.Markdown("📝 Here's a summary of your interview:")
        summary_text = gr.Markdown(label="Interview Summary", visible=False)
        download_btn = gr.File(label="Download Summary (TXT)", interactive=False)
        close_summary_btn = gr.Button("Close", variant="secondary")

    close_summary_btn.click(lambda: gr.update(visible=False), outputs=[summary_display_group])

    btn_yes.click(
        lambda: gr.update(visible=True),
        outputs=[progress_modal]
    ).then(
        end_interview_with_summary,
        inputs=[interview_application, state],
        outputs=[
            interview_chat, chosen_position_name, chosen_position_index,
            *interview_btns, confirm_modal, progress_modal,
            summary_display_group, summary_text, download_btn
        ]
    )

demo.launch()
