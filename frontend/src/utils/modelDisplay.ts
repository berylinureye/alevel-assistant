export interface AgentDisplay {
  shortName: string
  roleName: string
  description: string
}

const AGENT_DISPLAY: Record<string, AgentDisplay> = {
  'DeepSeek-Fast': {
    shortName: '快速批改',
    roleName: '答案与关键步骤',
    description: '先判断答案和关键步骤是否成立',
  },
  'Qwen-Fast': {
    shortName: '步骤检查',
    roleName: '过程完整性',
    description: '检查解题步骤和表达是否完整',
  },
  'GLM-Fast': {
    shortName: '答案核对',
    roleName: '计算与结果',
    description: '核对最终答案和明显计算问题',
  },
  'Qwen-Accurate': {
    shortName: '评分复核',
    roleName: '扣分点检查',
    description: '复核得分和扣分点是否合理',
  },
  'GLM-Thinking': {
    shortName: '深度复核',
    roleName: '复杂推理',
    description: '处理多步骤推理和不确定题目',
  },
}

export function getAgentDisplay(agentName: string | null | undefined): AgentDisplay {
  if (!agentName) {
    return {
      shortName: 'AI 批改员',
      roleName: '批改中',
      description: '正在检查本题答案',
    }
  }
  return AGENT_DISPLAY[agentName] ?? {
    shortName: 'AI 批改员',
    roleName: '智能批改',
    description: '正在检查本题答案',
  }
}

export function getAgentSortOrder(agentName: string): number {
  const order = Object.keys(AGENT_DISPLAY).indexOf(agentName)
  return order >= 0 ? order : 99
}
