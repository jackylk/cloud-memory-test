# Cloud Services API Research Report

**Date:** 2026-01-30
**Purpose:** Document APIs for cloud-based Knowledge Base and Memory services for benchmarking

---

## Table of Contents

1. [Knowledge Base Services](#knowledge-base-services)
   - [Google Dialogflow CX Data Store API](#1-google-dialogflow-cx-data-store-api)
   - [华为云 CSS (Cloud Search Service)](#2-华为云-css-cloud-search-service)
2. [Memory Services](#memory-services)
   - [AWS Bedrock AgentCore Memory](#1-aws-bedrock-agentcore-memory)
   - [Google Vertex AI Memory Bank](#2-google-vertex-ai-memory-bank)
   - [火山引擎 AgentKit Memory](#3-火山引擎-agentkit-memory)
   - [阿里云百炼长期记忆](#4-阿里云百炼长期记忆)

---

## Knowledge Base Services

### 1. Google Dialogflow CX Data Store API

#### Overview
Dialogflow CX provides data store handlers that enable LLM-generated agent responses based on website content and uploaded data. Data stores integrate with Dialogflow CX agents for conversational interactions.

#### Python SDK Package
```bash
pip install google-cloud-dialogflow-cx
```

**Package Name:** `google-cloud-dialogflow-cx`
**PyPI:** https://pypi.org/project/google-cloud-dialogflow-cx/

#### Authentication Method
Uses standard Google Cloud authentication:
- Service account keys
- Application Default Credentials (ADC)
- OAuth 2.0

```python
from google.cloud import dialogflowcx_v3beta1 as dialogflow

# Authentication handled through GOOGLE_APPLICATION_CREDENTIALS environment variable
# or gcloud auth application-default login
```

#### Key API Endpoints

**Sessions API (detectIntent):**
- **Purpose:** Send queries to the agent and receive responses
- **Endpoint:** `projects.locations.agents.sessions.detectIntent`
- **Method:** POST

**Query Structure:**
```python
from google.cloud.dialogflowcx_v3 import SessionsClient, QueryInput, TextInput

client = SessionsClient()
session_path = f"projects/{project_id}/locations/{location}/agents/{agent_id}/sessions/{session_id}"

# For text-based queries
text_input = TextInput(text="Your query here")
query_input = QueryInput(text=text_input, language_code="en")

response = client.detect_intent(
    request={
        "session": session_path,
        "query_input": query_input
    }
)
```

**Data Store Operations:**
- Data stores are configured through the agent and accessed via the detectIntent API
- Use `QueryParameters` to control data store behavior
- Set `populate_data_store_connection_signals` flag to get data store connection signals in response

#### Code Examples

**Basic Query:**
```python
from google.cloud.dialogflowcx_v3 import SessionsClient

client = SessionsClient()
session = f"projects/{PROJECT_ID}/locations/{LOCATION}/agents/{AGENT_ID}/sessions/{SESSION_ID}"

response = client.detect_intent(
    request={
        "session": session,
        "query_input": {
            "text": {"text": "What are your business hours?"},
            "language_code": "en"
        }
    }
)

print(f"Response: {response.query_result.response_messages}")
```

#### API Documentation Links
- [Python Client Library](https://cloud.google.com/dialogflow/cx/docs/reference/library/python)
- [Data Store Tools](https://docs.cloud.google.com/dialogflow/cx/docs/concept/data-store/handler)
- [Detect Intent API](https://cloud.google.com/dialogflow/cx/docs/reference/rest/v3/projects.locations.agents.sessions/detectIntent)
- [Google Codelabs: Data Stores](https://codelabs.developers.google.com/codelabs/dialogflow-generator)
- [Python Samples Repository](https://github.com/GoogleCloudPlatform/python-docs-samples/tree/main/dialogflow-cx)

---

### 2. 华为云 CSS (Cloud Search Service)

#### Overview
Cloud Search Service (CSS) is a fully managed distributed search service based on Elasticsearch, providing structured/unstructured text search and AI vector-based multi-condition retrieval.

#### Python SDK Package
```bash
pip install huaweicloudsdkcore
pip install huaweicloudsdkcss
```

**Package Name:** `huaweicloudsdkcss`
**PyPI:** https://pypi.org/project/huaweicloudsdkcss/

#### Authentication Method
Uses Huawei Cloud AK/SK (Access Key/Secret Key) authentication:

```python
from huaweicloudsdkcore.auth.credentials import BasicCredentials
import os

# CRITICAL: Do not hard-code credentials
credentials = BasicCredentials(
    os.getenv("HUAWEICLOUD_SDK_AK"),
    os.getenv("HUAWEICLOUD_SDK_SK")
)
```

**Environment Variables:**
- `HUAWEICLOUD_SDK_AK` - Access Key
- `HUAWEICLOUD_SDK_SK` - Secret Key

#### Key API Endpoints

CSS uses Elasticsearch REST APIs for data operations:

**Document Operations:**
- **Upload Document:** POST `/{index}/_doc/{id}`
- **Bulk Upload:** POST `/_bulk`
- **Search:** POST `/{index}/_search`
- **Delete Document:** DELETE `/{index}/_doc/{id}`

**Cluster Management (via SDK):**
- `CreateCluster` - Create CSS cluster
- `ListClustersDetails` - Query cluster list
- `DeleteCluster` - Delete cluster

#### Code Examples

**Basic Client Setup:**
```python
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcss.v1 import CssClient
from huaweicloudsdkcss.v1.region.css_region import CssRegion
import os

credentials = BasicCredentials(
    os.getenv("HUAWEICLOUD_SDK_AK"),
    os.getenv("HUAWEICLOUD_SDK_SK")
)

client = CssClient.new_builder() \
    .with_credentials(credentials) \
    .with_region(CssRegion.CN_NORTH_4) \
    .build()
```

**Search Operations:**
CSS uses standard Elasticsearch APIs for search operations. After creating a cluster, use the Elasticsearch Python client with the cluster endpoint:

```python
from elasticsearch import Elasticsearch

es = Elasticsearch(
    hosts=["https://your-css-cluster-endpoint:9200"],
    http_auth=('username', 'password'),
    verify_certs=True
)

# Search documents
response = es.search(
    index="your_index",
    body={
        "query": {
            "match": {
                "content": "search query"
            }
        }
    }
)
```

#### API Documentation Links
- [SDK Overview](https://support.huaweicloud.com/intl/en-us/sdkreference-css/css_01_0330.html)
- [CSS Product Page](https://www.huaweicloud.com/intl/en-us/product/css.html)
- [API Reference](https://support.huaweicloud.com/intl/en-us/api-css/cluster_management.html)
- [GitHub Repository](https://github.com/huaweicloud/huaweicloud-sdk-python-v3)
- [API Explorer](https://console.huaweicloud.com/apiexplorer) - Generates SDK code dynamically

#### Notes
- CSS is essentially Elasticsearch-as-a-Service
- Use Huawei Cloud SDK for cluster management
- Use standard Elasticsearch client for data operations (index, search, delete)
- API Explorer provides auto-generated code samples

---

## Memory Services

### 1. AWS Bedrock AgentCore Memory

#### Overview
Amazon Bedrock AgentCore Memory provides both short-term memory (STM) for conversation persistence and long-term memory (LTM) for extracting and storing user preferences, facts, and session summaries.

#### Python SDK Package
```bash
pip install bedrock-agentcore
pip install bedrock-agentcore-starter-toolkit
```

**Package Names:**
- `bedrock-agentcore` - Core SDK
- `bedrock-agentcore-starter-toolkit` - High-level wrapper
- Standard boto3 also provides access via `bedrock-agentcore-control` and `bedrock-agentcore` services

**Requirements:** Python 3.10+

#### Authentication Method
Uses standard AWS authentication:

```bash
aws configure
```

Supports:
- AWS credentials file (`~/.aws/credentials`)
- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- IAM roles (for EC2/Lambda)
- AWS SSO

#### Key API Endpoints

**Memory Management:**
- `create_memory` - Create memory resource
- `get_memory` - Retrieve memory details
- `list_memories` - List all memories
- `delete_memory` - Remove memory resource

**Event Operations:**
- `create_event` - Add conversation turns/events
- `list_events` - Retrieve conversation history
- `get_event` - Get specific event

**Long-Term Memory:**
- `list_long_term_memory_records` - Get extracted memories
- `search_long_term_memories` - Semantic search across memories

#### Code Examples

**1. Create Memory Resource:**

Using Starter Toolkit:
```python
from bedrock_agentcore_starter_toolkit.operations.memory.manager import MemoryManager
from bedrock_agentcore_starter_toolkit.operations.memory.models.strategies import SemanticStrategy

memory_manager = MemoryManager(region_name="us-west-2")

memory = memory_manager.get_or_create_memory(
    name="CustomerSupportMemory",
    description="Memory store for customer support conversations",
    strategies=[
        SemanticStrategy(
            name="semanticLongTermMemory",
            namespaces=['/strategies/{memoryStrategyId}/actors/{actorId}/'],
        )
    ]
)

print(f"Memory ID: {memory.get('id')}")
```

Using boto3 MemoryClient:
```python
from bedrock_agentcore.memory import MemoryClient

client = MemoryClient(region_name="us-east-1")

memory = client.create_memory(
    name="CustomerSupportAgentMemory",
    description="Memory for customer support conversations",
)

memory_id = memory.get("id")
```

**2. Create Events (Add Conversation Turns):**

```python
from bedrock_agentcore.memory.session import MemorySessionManager
from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

# Create session
session_manager = MemorySessionManager(
    memory_id=memory.get("id"),
    region_name="us-west-2"
)

session = session_manager.create_memory_session(
    actor_id="User123",
    session_id="SupportSession456"
)

# Add conversation turns
session.add_turns(
    messages=[
        ConversationalMessage(
            "Hi, I need help with my order #12345",
            MessageRole.USER
        ),
        ConversationalMessage(
            "I'll help you with that order. Let me look it up.",
            MessageRole.ASSISTANT
        )
    ]
)
```

Using MemoryClient directly:
```python
client.create_event(
    memory_id=memory_id,
    actor_id="User84",
    session_id="OrderSession1",
    messages=[
        ("Hi, I'm having trouble with my order #12345", "USER"),
        ("I'm sorry to hear that. Let me look up your order.", "ASSISTANT"),
        ("lookup_order(order_id='12345')", "TOOL"),
    ]
)
```

**3. Retrieve Short-Term Memory (Events):**

```python
# Get last K turns from session
turns = session.get_last_k_turns(k=5)

for turn in turns:
    print(f"Turn: {turn}")
```

**4. Retrieve Long-Term Memory:**

```python
# List all memory records
memory_records = session.list_long_term_memory_records(
    namespace_prefix="/"
)

for record in memory_records:
    print(f"Memory record: {record}")

# Semantic search
memory_records = session.search_long_term_memories(
    query="customer preferences",
    namespace_prefix="/",
    top_k=3
)
```

**5. Delete Memory:**

```python
memory_manager.delete_memory(memory_id=memory.get("id"))
```

#### Memory Strategies

Three built-in strategies:

1. **Summary Memory Strategy** - Summarizes conversation sessions
2. **User Preference Memory Strategy** - Learns and stores user preferences
3. **Semantic Memory Strategy** - Extracts factual information automatically

```python
strategies=[
    {
        "summaryMemoryStrategy": {
            "name": "SessionSummarizer",
            "namespaces": ["/summaries/{actorId}/{sessionId}"]
        }
    },
    {
        "userPreferenceMemoryStrategy": {
            "name": "PreferenceLearner",
            "namespaces": ["/preferences/{actorId}"]
        }
    },
    {
        "semanticMemoryStrategy": {
            "name": "FactExtractor",
            "namespaces": ["/facts/{actorId}"]
        }
    }
]
```

#### API Documentation Links
- [Get Started with AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-get-started.html)
- [AgentCore SDK Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-sdk-memory.html)
- [Memory Quickstart](https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/memory/quickstart.html)
- [GitHub Repository](https://github.com/aws/bedrock-agentcore-sdk-python)
- [Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-agentcore-control.html)
- [Short-term Memory Operations](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/short-term-memory-operations.html)

---

### 2. Google Vertex AI Memory Bank

#### Overview
Vertex AI Agent Engine Memory Bank provides both short-term (sessions) and long-term (persistent memory) storage for conversational agents. Sessions store individual interactions, while Memory Bank retrieves and personalizes agent interactions across sessions.

#### Python SDK Package
```bash
pip install google-cloud-aiplatform
# or
pip install vertexai
```

**Package Name:** `vertexai` (Vertex AI SDK)
**Status:** General Availability (GA) as of 2026

#### Authentication Method
Uses Google Cloud authentication:
- Service account keys
- Application Default Credentials
- gcloud CLI authentication

```python
import vertexai

client = vertexai.Client(
    project="PROJECT_ID",
    location="LOCATION"
)
```

#### Key API Endpoints

**Session Management:**
- `sessions.create()` - Create new session
- `sessions.get()` - Retrieve session
- `sessions.list()` - List sessions
- `sessions.delete()` - Remove session

**Event Operations:**
- `sessions.events.append()` - Add conversation events to session
- `sessions.events.list()` - Retrieve session events

**Memory Operations:**
- `memories.create()` - Create memory directly
- `memories.generate()` - Generate memories from session history
- `memories.retrieve()` - Fetch memories for context
- `memories.list()` - List all memories
- `memories.delete()` - Remove memories

#### Code Examples

**1. Initialize Client:**

```python
import vertexai

client = vertexai.Client(
    project="my-project-id",
    location="us-central1"
)
```

**2. Create Session:**

```python
session = client.agent_engines.sessions.create(
    name="projects/PROJECT_ID/locations/LOCATION/agentEngines/AGENT_ENGINE_NAME",
    user_id="user123"
)

print(f"Session: {session.response.name}")
```

**3. Append Events to Session:**

```python
import datetime

# Add user message
client.agent_engines.sessions.events.append(
    name=session.response.name,
    author="user",
    invocation_id="1",
    timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    config={
        "content": {
            "role": "user",
            "parts": [{"text": "Hello, I'm looking for restaurant recommendations"}]
        }
    }
)

# Add assistant response
client.agent_engines.sessions.events.append(
    name=session.response.name,
    author="assistant",
    invocation_id="2",
    timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    config={
        "content": {
            "role": "model",
            "parts": [{"text": "I'd be happy to help! What type of cuisine do you prefer?"}]
        }
    }
)
```

**4. Generate Memories from Session:**

```python
# Generate memories from conversation history
client.agent_engines.memories.generate(
    name=agent_engine.api_resource.name,
    vertex_session_source={
        "session": session.response.name
    },
    scope={"user_id": "user123"}
)
```

**5. Retrieve Memories:**

```python
# Fetch memories for a user
retrieved_memories = list(
    client.agent_engines.memories.retrieve(
        name=agent_engine.api_resource.name,
        scope={"user_id": "user123"}
    )
)

for memory in retrieved_memories:
    print(f"Memory: {memory}")
```

**6. Create Direct Memory (without session consolidation):**

```python
memory = client.agent_engines.memories.create(
    name=agent_engine.api_resource.name,
    fact="User prefers Italian restaurants in downtown area",
    scope={"user_id": "user123"}
)
```

**7. Delete Memory:**

```python
client.agent_engines.memories.delete(
    name=f"{agent_engine.api_resource.name}/memories/{memory_id}"
)
```

#### Integration with Agent Development Kit (ADK)

```python
from google_ai_adk.sessions import VertexAiMemoryBankService

# Connect agent to Memory Bank
memory_service = VertexAiMemoryBankService(
    project_id="my-project",
    location="us-central1",
    agent_engine_name="my-agent-engine"
)

# Memory is automatically managed across sessions
```

#### API Documentation Links
- [Agent Engine Memory Bank Quickstart](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/quickstart-api)
- [Memory Bank Setup](https://docs.cloud.google.com/agent-builder/agent-engine/memory-bank/set-up)
- [Agent Engine Overview](https://docs.cloud.google.com/agent-builder/agent-engine/overview)
- [Memory Bank Announcement](https://cloud.google.com/blog/products/ai-machine-learning/vertex-ai-memory-bank-in-public-preview)
- [ADK Memory Documentation](https://google.github.io/adk-docs/sessions/memory/)
- [Python SDK Introduction](https://docs.cloud.google.com/vertex-ai/docs/python-sdk/use-vertex-ai-python-sdk)

---

### 3. 火山引擎 AgentKit Memory

#### Overview
Volcengine (火山引擎) AgentKit Memory provides a persistent storage solution for AI Agents, supporting the storage of agent states, memories, and other data in a secure and scalable manner.

#### Python SDK Package
```bash
# Stable release
pip install agentkit-sdk-python

# Pre-release version (may contain bugs)
pip install --pre agentkit-sdk-python

# Specific version
pip install agentkit-sdk-python==1.0.0.dev1
```

**Package Name:** `agentkit-sdk-python`
**PyPI:** https://pypi.org/project/agentkit-sdk-python/
**License:** Apache 2.0

#### Alternative SDK - VikingDB (for memory operations)
```bash
pip install vikingdb-python-sdk
```

VikingDB provides the underlying storage for memory operations.

#### Authentication Method

AgentKit uses Volcengine IAM authentication. Typically requires:
- Access Key ID
- Secret Access Key
- Region

```python
from agentkit import AgentKitClient

# Authentication details typically passed during client initialization
client = AgentKitClient(
    access_key_id="YOUR_ACCESS_KEY",
    secret_access_key="YOUR_SECRET_KEY",
    region="cn-beijing"
)
```

For VikingDB Memory:
```python
from vikingdb import IAM
from vikingdb.memory import VikingMem

# Initialize with IAM credentials
iam = IAM(
    access_key="YOUR_ACCESS_KEY",
    secret_key="YOUR_SECRET_KEY"
)

memory_client = VikingMem(iam=iam)
```

#### Key API Endpoints

Based on available documentation:

**Memory Operations:**
- Create memory collection
- Add session messages (user-assistant conversations)
- Search memories with filters
- Retrieve conversation history
- Delete memory records

**Session Management:**
- Create sessions
- Store conversation state
- Retrieve session context

#### Code Examples

**VikingDB Memory Example:**

```python
from vikingdb import IAM
from vikingdb.memory import VikingMem

# Initialize client
iam = IAM(
    access_key="YOUR_ACCESS_KEY",
    secret_key="YOUR_SECRET_KEY"
)

memory = VikingMem(iam=iam)

# Get or create collection
collection = memory.get_collection("my_memory_collection")

# Add session messages
collection.add_session(
    session_id="session_001",
    messages=[
        {"role": "user", "content": "What's the weather like?"},
        {"role": "assistant", "content": "The weather is sunny today."}
    ]
)

# Search memories
results = collection.search(
    query="weather",
    filters={"session_id": "session_001"},
    top_k=5
)

for result in results:
    print(f"Memory: {result}")
```

**AgentKit SDK Pattern (conceptual):**

```python
from agentkit import AgentKitClient
from agentkit.memory import MemoryManager

# Initialize client
client = AgentKitClient(
    access_key_id="YOUR_ACCESS_KEY",
    secret_access_key="YOUR_SECRET_KEY",
    region="cn-beijing"
)

# Create memory manager
memory_manager = MemoryManager(client)

# Store memory
memory_manager.store(
    user_id="user_123",
    session_id="session_456",
    content={
        "query": "What are your business hours?",
        "response": "We're open 9 AM to 5 PM weekdays.",
        "timestamp": "2026-01-30T10:00:00Z"
    }
)

# Retrieve memories
memories = memory_manager.retrieve(
    user_id="user_123",
    limit=10
)
```

#### API Documentation Links
- [GitHub Repository](https://github.com/volcengine/agentkit-sdk-python)
- [Official Documentation](https://volcengine.github.io/agentkit-sdk-python/)
- [Memory Quick Start](https://volcengine.github.io/agentkit-sdk-python/content/6.memory/1.memory_quickstart.html)
- [Sample Projects](https://github.com/volcengine/agentkit-samples)
- [VikingDB SDK](https://github.com/volcengine/vikingdb-python-sdk)
- [Volcengine AgentKit Docs](https://www.volcengine.com/docs/86681/1844823) (Chinese)
- [SDK Overview](https://www.volcengine.com/docs/86681/2085106) (Chinese, updated Jan 2026)

#### Notes
- Development versions may contain bugs, not recommended for production
- Documentation available in Chinese and English
- VeADK (Volcengine Agent Development Kit) is another related SDK: https://github.com/volcengine/veadk-python
- Memory functionality provided through VikingDB backend

---

### 4. 阿里云百炼长期记忆

#### Overview
Alibaba Cloud Bailian (阿里云百炼) Long-Term Memory enables intelligent agent applications to store and retrieve personalized information (user features, preferences, etc.) across conversations. The system automatically extracts and stores relevant information as memory nodes during conversations.

#### Python SDK Package
```bash
pip install alibabacloud_bailian20231229
```

**Package Name:** `alibabacloud_bailian20231229`
**Note:** The version date `20231229` indicates API version dated December 29, 2023. There's also an earlier version: `alibabacloud_bailian20230601`

#### Authentication Method

Uses Alibaba Cloud AK/SK authentication:

```python
from alibabacloud_bailian20231229.client import Client
from alibabacloud_tea_openapi.models import Config

# CRITICAL: Do not hard-code credentials in production
config = Config(
    access_key_id=os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID'),
    access_key_secret=os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET'),
    endpoint='bailian.cn-beijing.aliyuncs.com',  # Adjust region as needed
    region_id='cn-beijing'
)

client = Client(config)
```

**Environment Variables:**
- `ALIBABA_CLOUD_ACCESS_KEY_ID` - Access Key ID
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET` - Access Key Secret

**Authentication Permission:** RAM (Resource Access Management)
**Required Action:** `sfm:CreateMemory` (and related memory actions)

#### Key API Endpoints

**Memory Management:**
- `CreateMemory` - 创建长期记忆体 (Create long-term memory)
- `GetMemory` - 获取记忆体信息 (Retrieve memory information)
- `ListMemories` - 获取长期记忆体列表 (List memories)
- `DeleteMemory` - 删除记忆体 (Delete memory)

**Memory Node Operations:**
- `CreateMemoryNode` - 创建记忆片段 (Create memory nodes/fragments)
- `GetMemoryNode` - 获取记忆片段 (Get memory node)
- `ListMemoryNodes` - 获取记忆片段列表 (List memory nodes)
- `UpdateMemoryNode` - 更新记忆片段 (Update memory node)
- `DeleteMemoryNode` - 删除记忆片段 (Delete memory node)

#### Code Examples

**1. Create Memory:**

```python
from alibabacloud_bailian20231229.client import Client
from alibabacloud_bailian20231229 import models as bailian_models
from alibabacloud_tea_openapi.models import Config
import os

# Initialize client
config = Config(
    access_key_id=os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID'),
    access_key_secret=os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET'),
    endpoint='bailian.cn-beijing.aliyuncs.com',
    region_id='cn-beijing'
)

client = Client(config)

# Create memory
request = bailian_models.CreateMemoryRequest(
    workspace_id="llm-3z7uw7fwz0vexxxx",
    description="User profile memory"
)

response = client.create_memory(request)
memory_id = response.body.memory_id
print(f"Created memory ID: {memory_id}")
```

**API Request Structure:**
- **Method:** POST
- **Path:** `/{workspaceId}/memories`
- **Response:** Returns `memoryId` and `requestId`

**2. Get Memory:**

```python
request = bailian_models.GetMemoryRequest(
    workspace_id="llm-3z7uw7fwz0vexxxx",
    memory_id=memory_id
)

response = client.get_memory(request)
print(f"Memory details: {response.body}")
```

**3. Create Memory Node:**

Memory nodes are typically created automatically during agent conversations, but can also be created manually:

```python
request = bailian_models.CreateMemoryNodeRequest(
    workspace_id="llm-3z7uw7fwz0vexxxx",
    memory_id=memory_id,
    content="User prefers vegetarian restaurants"
)

response = client.create_memory_node(request)
node_id = response.body.memory_node_id
```

**4. List Memory Nodes:**

```python
request = bailian_models.ListMemoryNodesRequest(
    workspace_id="llm-3z7uw7fwz0vexxxx",
    memory_id=memory_id
)

response = client.list_memory_nodes(request)
for node in response.body.memory_nodes:
    print(f"Memory node: {node.content}")
```

**5. Update Memory Node:**

```python
request = bailian_models.UpdateMemoryNodeRequest(
    workspace_id="llm-3z7uw7fwz0vexxxx",
    memory_id=memory_id,
    memory_node_id=node_id,
    content="User prefers Italian and vegetarian restaurants"
)

response = client.update_memory_node(request)
```

**6. Delete Memory Node:**

```python
request = bailian_models.DeleteMemoryNodeRequest(
    workspace_id="llm-3z7uw7fwz0vexxxx",
    memory_id=memory_id,
    memory_node_id=node_id
)

response = client.delete_memory_node(request)
```

**7. Delete Memory:**

```python
request = bailian_models.DeleteMemoryRequest(
    workspace_id="llm-3z7uw7fwz0vexxxx",
    memory_id=memory_id
)

response = client.delete_memory(request)
```

**8. Using Memory in Agent Calls:**

When calling an agent application, pass the `memoryId`:

```python
# Conceptual example - actual API may vary
agent_request = bailian_models.InvokeAgentRequest(
    workspace_id="llm-3z7uw7fwz0vexxxx",
    app_id="your_app_id",
    memory_id=memory_id,
    prompt="What restaurants do I like?"
)

response = client.invoke_agent(agent_request)
# System automatically recalls memory content and includes it in model context
```

#### Important Notes

**Rate Limiting:**
- Ensure at least 1 second between requests to avoid rate limiting (限流说明：请确保两次请求间隔至少 1 秒)

**Memory Auto-Creation:**
- When calling an agent application via API with `memoryId`, the system automatically creates MemoryNodes based on conversation records
- Memory extraction happens automatically during conversations

**Workspace ID:**
- Found in the workspace settings (工作空间设置)
- Required for all memory operations

**Description Constraints:**
- 1-50 characters
- Supports Unicode letters, colons, underscores, periods, hyphens

#### API Documentation Links
- [Long-Term Memory Guide](https://help.aliyun.com/zh/model-studio/long-term-memory) (Chinese)
- [CreateMemory API Reference](https://help.aliyun.com/zh/model-studio/developer-reference/api-bailian-2023-12-29-creatememory) (Chinese)
- [GetMemory API Reference](https://help.aliyun.com/zh/model-studio/api-bailian-2023-12-29-getmemory) (Chinese)
- [User Guide](https://help.aliyun.com/zh/model-studio/user-guide/long-term-memory) (Chinese)
- [Knowledge Base API Guide](https://help.aliyun.com/zh/model-studio/rag-knowledge-base-api-guide) (Chinese)
- [Application Calling Guide](https://www.alibabacloud.com/help/zh/model-studio/application-calling-guide) (Chinese/English)
- [Model Studio SDK Installation](https://www.alibabacloud.com/help/en/model-studio/install-sdk)
- [OpenAPI Explorer](https://api.aliyun.com/api/bailian/2023-12-29/CreateMemory) - Auto-generates SDK examples

#### Additional Resources
- [DashScope API Reference](https://dashscope.aliyun.com/) - Search "长期记忆" for more examples
- [Agent Memory Technical Deep Dive](https://www.cnblogs.com/alisystemsoftware/p/19417127) (Chinese)
- [MemoryScope Open Source Project](https://github.com/modelscope/memscope) - Alibaba's open-source agent memory framework

---

## Summary Comparison Table

| Service | SDK Package | Auth Method | Primary Query Method | Memory Type |
|---------|-------------|-------------|---------------------|-------------|
| **Google Dialogflow CX** | `google-cloud-dialogflow-cx` | Google Cloud ADC | `detectIntent()` | Knowledge Base (Data Store) |
| **华为云 CSS** | `huaweicloudsdkcss` | AK/SK (env vars) | Elasticsearch API `/_search` | Knowledge Base (Search) |
| **AWS Bedrock AgentCore** | `bedrock-agentcore` | AWS credentials | `create_event()`, `search_long_term_memories()` | Short-term & Long-term Memory |
| **Google Vertex AI** | `vertexai` | Google Cloud ADC | `sessions.events.append()`, `memories.retrieve()` | Session & Memory Bank |
| **火山引擎 AgentKit** | `agentkit-sdk-python` | IAM AK/SK | VikingDB `search()`, `add_session()` | Persistent Memory Storage |
| **阿里云百炼** | `alibabacloud_bailian20231229` | AK/SK (env vars) | `CreateMemoryNode()`, `ListMemoryNodes()` | Long-term Memory (Auto-extracted) |

---

## Key Benchmarking Considerations

### For Knowledge Base Services:

1. **Query Latency:** Time from query submission to response
2. **Retrieval Accuracy:** Quality of retrieved documents/responses
3. **Throughput:** Queries per second (QPS) capacity
4. **Document Upload Time:** Time to index documents
5. **Delete Performance:** Time to remove documents

### For Memory Services:

1. **Write Latency:** Time to store memory/events
2. **Read Latency:** Time to retrieve memories
3. **Search Performance:** Semantic search speed and accuracy
4. **Memory Generation Time:** Time to extract long-term memories from events
5. **Session Context Handling:** Number of conversation turns supported
6. **Delete Performance:** Time to remove memories

### Rate Limits to Consider:

- **AWS Bedrock:** Standard AWS service quotas apply
- **Google Cloud:** Quotas per project/region
- **Alibaba Bailian:** Minimum 1-second interval between requests
- **Huawei CSS:** Depends on cluster configuration
- **Volcengine:** Check service documentation for limits

---

## Next Steps for Implementation

1. **Create Adapter Classes:** Implement adapters for each service following the existing adapter pattern
2. **Authentication Setup:** Configure environment variables and credentials for each cloud service
3. **Test Data Preparation:** Create standardized test datasets for benchmarking
4. **Metric Collection:** Ensure consistent metric collection across all adapters
5. **Error Handling:** Implement retry logic and rate limiting for each service
6. **Cost Tracking:** Monitor API costs during benchmarking

---

## Sources

### Google Dialogflow CX
- [Data store tools | Dialogflow CX](https://docs.cloud.google.com/dialogflow/cx/docs/concept/data-store/handler)
- [google-cloud-dialogflow-cx · PyPI](https://pypi.org/project/google-cloud-dialogflow-cx/)
- [Python client library | Dialogflow CX](https://cloud.google.com/dialogflow/cx/docs/reference/library/python)
- [Informed decision making using Dialogflow CX generators and data stores](https://codelabs.developers.google.com/codelabs/dialogflow-generator)
- [python-docs-samples/dialogflow-cx](https://github.com/GoogleCloudPlatform/python-docs-samples/tree/main/dialogflow-cx)

### 华为云 CSS
- [SDK Overview | Cloud Search Service](https://support.huaweicloud.com/intl/en-us/sdkreference-css/css_01_0330.html)
- [huaweicloudsdkcss · PyPI](https://pypi.org/project/huaweicloudsdkcss/3.1.109/)
- [GitHub - huaweicloud/huaweicloud-sdk-python-v3](https://github.com/huaweicloud/huaweicloud-sdk-python-v3)
- [Cloud Search Service Product Page](https://www.huaweicloud.com/intl/en-us/product/css.html)

### AWS Bedrock AgentCore Memory
- [Get started with AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-get-started.html)
- [Amazon Bedrock AgentCore SDK](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-sdk-memory.html)
- [Memory Quickstart](https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/memory/quickstart.html)
- [GitHub - aws/bedrock-agentcore-sdk-python](https://github.com/aws/bedrock-agentcore-sdk-python)
- [Amazon Bedrock AgentCore Memory Blog](https://aws.amazon.com/blogs/machine-learning/amazon-bedrock-agentcore-memory-building-context-aware-agents/)

### Google Vertex AI Memory Bank
- [Quickstart with Vertex AI Agent Engine SDK](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/quickstart-api)
- [Vertex AI Memory Bank in public preview](https://cloud.google.com/blog/products/ai-machine-learning/vertex-ai-memory-bank-in-public-preview)
- [Set up Memory Bank](https://docs.cloud.google.com/agent-builder/agent-engine/memory-bank/set-up)
- [Memory - Agent Development Kit](https://google.github.io/adk-docs/sessions/memory/)

### 火山引擎 AgentKit
- [GitHub - volcengine/agentkit-sdk-python](https://github.com/volcengine/agentkit-sdk-python)
- [AgentKit Documentation](https://volcengine.github.io/agentkit-sdk-python/)
- [什么是AgentKit | 火山引擎](https://www.volcengine.com/docs/86681/1844823)
- [SDK概述 | 火山引擎](https://www.volcengine.com/docs/86681/2085106)
- [GitHub - volcengine/vikingdb-python-sdk](https://github.com/volcengine/vikingdb-python-sdk)

### 阿里云百炼
- [长期记忆 | 阿里云](https://help.aliyun.com/zh/model-studio/long-term-memory)
- [CreateMemory API](https://help.aliyun.com/zh/model-studio/developer-reference/api-bailian-2023-12-29-creatememory)
- [GetMemory API](https://help.aliyun.com/zh/model-studio/api-bailian-2023-12-29-getmemory)
- [Long-term Memory User Guide](https://help.aliyun.com/zh/model-studio/user-guide/long-term-memory)
- [Install the Alibaba Cloud Model Studio SDK](https://www.alibabacloud.com/help/en/model-studio/install-sdk)

---

**End of Report**
