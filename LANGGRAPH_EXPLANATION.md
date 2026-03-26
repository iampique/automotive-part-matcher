# LangGraph Usage Explanation

## Overview

LangGraph is used in this project to orchestrate the multi-step workflow for matching automotive connectors. It provides a structured, stateful way to execute complex AI-powered workflows with proper error handling, execution tracing, and visualization.

## Location

**File**: `backend/app/agent.py`

**Class**: `PartMatcherAgent`

## What is LangGraph?

LangGraph is a library for building stateful, multi-actor applications with LLMs. It allows you to define workflows as graphs where:
- **Nodes** represent individual steps/operations
- **Edges** define the flow between steps
- **State** flows through the graph, allowing each node to read and update shared data

## How It's Used in This Project

### 1. Workflow Definition

The workflow is defined as a **4-node sequential graph**:

```python
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("parse_requirements", self._parse_requirements_node)
workflow.add_node("search_qdrant", self._search_node)
workflow.add_node("score_matches", self._score_node)
workflow.add_node("rank_results", self._rank_node)

# Define execution flow
workflow.set_entry_point("parse_requirements")
workflow.add_edge("parse_requirements", "search_qdrant")
workflow.add_edge("search_qdrant", "score_matches")
workflow.add_edge("score_matches", "rank_results")
workflow.add_edge("rank_results", END)
```

### 2. State Management

LangGraph uses a **TypedDict** called `AgentState` to manage state across nodes:

```python
class AgentState(TypedDict):
    input_text: str  # Original user input
    parsed_requirements: Optional[CustomerRequirement]  # Extracted requirements
    search_results: List[Tuple[Connector, float]]  # Search candidates
    scored_matches: List[MatchResult]  # Scored matches
    final_results: List[MatchResult]  # Final ranked results
    error: Optional[str]  # Error messages
    execution_trace: List[Dict]  # For visualization
    acorn_used: bool  # ACORN algorithm flag
    enable_acorn: bool  # User preference
    hybrid_search_used: bool  # Hybrid search flag
    hybrid_search_metadata: Optional[Dict]  # Hybrid search details
```

Each node can:
- **Read** from the state
- **Update** the state
- **Pass** updated state to the next node

### 3. Node Implementation

Each node is a function that:
- Takes `AgentState` as input
- Performs its operation (LLM call, search, scoring, etc.)
- Updates the state
- Logs execution trace
- Returns updated state

**Example - Parse Requirements Node**:
```python
def _parse_requirements_node(self, state: AgentState) -> AgentState:
    start_time = time.time()
    
    # Extract requirements using LLM
    parsed_requirements = self.llm_service.extract_requirements(state["input_text"])
    
    # Update state
    state["parsed_requirements"] = parsed_requirements
    
    # Log execution trace
    state["execution_trace"].append({
        "node": "parse",
        "duration_ms": (time.time() - start_time) * 1000,
        "output": "Extracted requirements...",
        "status": "success"
    })
    
    return state
```

### 4. Execution Flow

When `agent.run()` is called:

1. **parse_requirements** node executes:
   - Takes `input_text` from state
   - Calls LLM service to extract structured requirements
   - Updates `parsed_requirements` in state
   - Logs execution trace

2. **search_qdrant** node executes:
   - Reads `parsed_requirements` from state
   - Generates embedding and searches Qdrant
   - Updates `search_results` in state
   - Logs execution trace (including ACORN usage)

3. **score_matches** node executes:
   - Reads `search_results` from state
   - Scores each connector using hybrid algorithm
   - Updates `scored_matches` in state
   - Logs execution trace

4. **rank_results** node executes:
   - Reads `scored_matches` from state
   - Ranks and selects top 10 results
   - Updates `final_results` in state
   - Logs execution trace

### 5. Execution Trace

Each node logs its execution details, which are used for:
- **Visualization**: The frontend displays a workflow trace showing each step
- **Debugging**: Developers can see exactly what happened at each step
- **Performance Monitoring**: Track how long each step takes

The trace includes:
- Node name
- Duration (milliseconds)
- Output summary
- Status (success/error)
- ACORN usage flag (for search node)

## Benefits of Using LangGraph

### 1. **Structured Workflow**
- Clear separation of concerns
- Easy to understand execution flow
- Simple to add/remove/modify steps

### 2. **State Management**
- Type-safe state flow
- Each node can access previous results
- No need for complex state passing

### 3. **Error Handling**
- Errors can be caught at each node
- State can include error messages
- Workflow can gracefully handle failures

### 4. **Observability**
- Built-in execution tracing
- Easy to visualize workflow execution
- Performance metrics per step

### 5. **Extensibility**
- Easy to add new nodes (e.g., filtering, validation)
- Can add conditional edges (if/else logic)
- Can add loops for iterative processing

## Example Execution

**Input**: "Need 48-pin connector for EV battery, 48V rated, IP67"

**Execution**:
1. **Parse** (1.2s): Extracts structured requirements
   - Pin count: 48
   - Voltage: 48V
   - IP rating: IP67
   - Application: EV battery

2. **Search** (0.8s): Searches Qdrant with filters
   - Found 50 candidates
   - ACORN: Not used (simple query)

3. **Score** (0.3s): Scores each candidate
   - Hard requirements: Pass/fail
   - Soft requirements: 0-100 score
   - 35 connectors passed hard requirements

4. **Rank** (<0.1s): Selects top 10
   - Sorted by score
   - Top 10 returned

**Output**: List of 10 ranked connectors with scores and explanations

## Visualization

The execution trace is visualized in the frontend:
- **WorkflowTrace component** shows each step
- Displays timing, status, and output
- Shows ACORN usage indicator
- Provides performance summary

## Future Enhancements

LangGraph makes it easy to add:
- **Conditional branching**: Different paths based on query type
- **Parallel processing**: Multiple searches in parallel
- **Iterative refinement**: Loop back to improve results
- **Validation nodes**: Check requirements before processing
- **Caching nodes**: Cache frequently searched requirements

## Summary

LangGraph provides a clean, maintainable way to orchestrate the complex multi-step workflow of:
1. Parsing natural language requirements
2. Searching vector database
3. Scoring matches
4. Ranking results

It enables proper state management, error handling, and observability, making the system production-ready and easy to debug and extend.




