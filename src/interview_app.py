import uuid

from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.agent.interview_administrator.interview_administrator import InterviewAdministrator
from src.pojo.interview_graph_state import InterviewGraphState, HumanToAiIteration
from src.common.logger import init_logger
from src.interview_config import InterviewConfig

from src.agent.interview_agent import BaseInterviewAgent
from src.agent.interview_manager.interview_manager import InterviewManager
from src.agent.technical_lead.technical_lead import TechnicalLead


class InterviewApp:
    """
    Class represent the interview orchestration of agents
    It will create LangGraph implementation of agent flows together with conditions
    """
    TOOLS_AGENT_NAME = "tools"

    def __init__(self, chosen_position: str, cv_content: str):
        """
        Create InterviewOrchestration

        Args:
            chosen_position (str) - identifier of position which was choosen
        """
        # here init dict of all nodes
        self.interview_config = InterviewConfig.get_active_instance()
        self.interview_config.update_candidate_cv(cv_content)
        self.nodes_dict = {
            BaseInterviewAgent.INTERVIEW_MANAGER_AGENT_NAME:
                InterviewManager(self, chosen_position).agent_callback,
            BaseInterviewAgent.TECH_LEAD_AGENT_NAME:
                TechnicalLead(self, chosen_position).agent_callback,
            BaseInterviewAgent.INTERVIEW_ADMINISTRATOR_AGENT_NAME:
                InterviewAdministrator(self, chosen_position).agent_callback,
            self.TOOLS_AGENT_NAME:
                ToolNode(tools=BaseInterviewAgent.get_tools())
        }
        self.session_id = uuid.uuid4()
        self.logger = init_logger()
        self.compiled_graph = None

    def _create_graph_and_add_nodes(self) -> StateGraph:
        """
        Create StateGraph instance with all nodes

        Return:
            new instance of StateGraph
        """
        self.logger.info("Creating nodes and builder ....")
        # //////////////// First Initialization ////////////////

        graph_builder = StateGraph(InterviewGraphState)

        # //////////////// Create Nodes ////////////////

        for agent_name, callback_func in self.nodes_dict.items():
            graph_builder.add_node(agent_name, callback_func)

        return graph_builder

    def _add_edges_with_conditions(self, graph_builder: StateGraph):
        """
        Add edges with conditions into StateGraph

        Args:
            graph_builder - StateGraph where add the edges
        """
        self.logger.info("Creating edges ....")
        # start with interview agent
        graph_builder.add_edge(START, BaseInterviewAgent.INTERVIEW_MANAGER_AGENT_NAME)

        # routing from manager. You can see that only manager can end the super step
        graph_builder.add_conditional_edges(
            BaseInterviewAgent.INTERVIEW_MANAGER_AGENT_NAME,
            lambda graph_state: graph_state.next_agent,
            {
                BaseInterviewAgent.TECH_LEAD_AGENT_NAME: BaseInterviewAgent.TECH_LEAD_AGENT_NAME,
                BaseInterviewAgent.INTERVIEW_ADMINISTRATOR_AGENT_NAME: BaseInterviewAgent.INTERVIEW_ADMINISTRATOR_AGENT_NAME,
                "END": END
            })

        # return tools to origin agent
        graph_builder.add_conditional_edges(
            BaseInterviewAgent.TECH_LEAD_AGENT_NAME, tools_condition,
            self.TOOLS_AGENT_NAME)
        graph_builder.add_edge(
            self.TOOLS_AGENT_NAME,
            BaseInterviewAgent.TECH_LEAD_AGENT_NAME)
        # question generator and question evaluator return answer back to manager
        graph_builder.add_edge(
            BaseInterviewAgent.TECH_LEAD_AGENT_NAME,
            BaseInterviewAgent.INTERVIEW_MANAGER_AGENT_NAME)
        # Administrator acknowledge that that interview is end and send it to manager whi inform candidate
        graph_builder.add_edge(
            BaseInterviewAgent.INTERVIEW_ADMINISTRATOR_AGENT_NAME,
            BaseInterviewAgent.INTERVIEW_MANAGER_AGENT_NAME)

    def create_graph(self):
        """
        Create compiled graph
        """
        graph_builder = self._create_graph_and_add_nodes()
        self._add_edges_with_conditions(graph_builder)
        # add memory for whole session
        self.compiled_graph = graph_builder.compile(checkpointer=MemorySaver())

    def invoke_user_query(self, user_message: str, history):
        interview_step_state = InterviewGraphState(
            messages=[{"role": "user", "content": user_message}],
            iteration=[[
                HumanToAiIteration(
                    message_content=user_message,
                    subject_role="candidate"
                )
            ]],
            session_id=str(self.session_id)
        )
        graph_config = {
            "configurable": {
                "thread_id": self.session_id
            }
        }
        result = self.compiled_graph.invoke(
            interview_step_state,
            config=graph_config
        )
        manager_reply = {"role": "assistant", "content": result["messages"][-1].content}
        return manager_reply
