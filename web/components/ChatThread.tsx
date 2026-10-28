"use client";

import { AuiIf, ComposerPrimitive, MessagePrimitive, ThreadPrimitive } from "@assistant-ui/react";
import { Icon, type IconName } from "./Icon";

const jobCapabilities = [
  ["target", "查询岗位", "读取 2027 校招岗位和要求—证据结论", "列出目前最值得关注的 2027 校招岗位，并解释证据和核心缺口"],
  ["columns", "查看投递", "读取阶段、官网证据和事件时间线", "总结我当前的投递进度，并指出下一步需要跟进的事项"],
  ["mail", "处理邮件", "解释只读邮件建议并引导人工确认", "查看待确认的招聘邮件建议，并告诉我每封邮件为什么这样分类"],
] as [IconName, string, string, string][];

const generalSuggestions = [
  ["briefcase", "规划求职任务", "把岗位、投递和面试安排成今天可执行的清单", "根据我目前的求职数据，帮我规划今天最应该完成的任务"],
  ["file", "整理复杂信息", "提炼重点、风险和下一步行动", "我会提供一段复杂信息，请按重点、风险和下一步行动帮我整理"],
  ["sparkles", "调用合适模块", "先识别意图，再交给对应 Specialist", "告诉我 Fei 当前可以协助哪些任务，以及会如何选择模块"],
] as [IconName, string, string, string][];

export function ChatThread({ module }: { module: "general" | "job_search" }) {
  const isJob = module === "job_search";
  return <ThreadPrimitive.Root className="thread-root">
    <ThreadPrimitive.Viewport className="thread-viewport">
      <AuiIf condition={(state) => state.thread.isEmpty}>
        <section className="welcome">
          <div className="welcome-logo">F</div><p className="eyebrow">FEI ASSISTANT</p>
          <h2>{isJob ? "把求职过程变成可追溯的工作流" : "今天想先处理什么？"}</h2>
          <p className="welcome-copy">{isJob ? "这里负责求职对话；岗位、投递、邮件和面试数据请在工作区管理。" : "Fei 会处理通用请求，并在任务明确涉及求职时自动调用求职模块。"}</p>
          <div className="capability-grid">{(isJob ? jobCapabilities : generalSuggestions).map(([icon, title, text, prompt]) => <ThreadPrimitive.Suggestion className="capability-card" prompt={prompt} key={title}><span><Icon name={icon} size={16} /></span><div><strong>{title}</strong><p>{text}</p></div><Icon name="arrow" size={13} /></ThreadPrimitive.Suggestion>)}</div>
        </section>
      </AuiIf>
      <div className="messages"><ThreadPrimitive.Messages>{({ message }) => message.role === "user" ? <UserMessage /> : <AssistantMessage module={module} />}</ThreadPrimitive.Messages></div>
      <ThreadPrimitive.ViewportFooter className="composer-footer">
        <ComposerPrimitive.Root className="composer">
          <ComposerPrimitive.Input className="composer-input" placeholder={isJob ? "询问岗位分析、招聘邮件或面试复盘……" : "告诉 Fei 你要处理什么……"} rows={1} />
          <div className="composer-actions"><span className="input-tip">Enter 发送 · Shift + Enter 换行</span>
            <AuiIf condition={(state) => !state.thread.isRunning}><ComposerPrimitive.Send className="send-button">↑</ComposerPrimitive.Send></AuiIf>
            <AuiIf condition={(state) => state.thread.isRunning}><ComposerPrimitive.Cancel className="send-button stop">■</ComposerPrimitive.Cancel></AuiIf>
          </div>
        </ComposerPrimitive.Root>
        <p className="disclaimer">模型只提供分析建议；状态变更和外部操作均需用户确认。</p>
      </ThreadPrimitive.ViewportFooter>
    </ThreadPrimitive.Viewport>
  </ThreadPrimitive.Root>;
}

function UserMessage() { return <MessagePrimitive.Root className="message-row user-row"><div className="user-message"><MessagePrimitive.Parts /></div></MessagePrimitive.Root>; }
function AssistantMessage({ module }: { module: string }) { return <MessagePrimitive.Root className="message-row assistant-row"><div className="assistant-avatar">F</div><div className="assistant-content"><div className="message-author">Fei 智能助手{module === "job_search" ? " · 求职模块" : ""}</div><div className="assistant-message"><MessagePrimitive.Parts /></div></div></MessagePrimitive.Root>; }
