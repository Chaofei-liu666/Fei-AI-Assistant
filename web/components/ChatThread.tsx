"use client";

import { AuiIf, ComposerPrimitive, MessagePrimitive, ThreadPrimitive } from "@assistant-ui/react";

const jobCapabilities = [
  ["▤", "分析岗位", "用简历证据核对 JD，不生成伪精确分数"],
  ["◇", "管理投递", "状态看板、事件时间线和可确认的邮件建议"],
  ["◉", "复盘面试", "确认转写后逐项分析回答并生成练习题"],
];

export function ChatThread({ module }: { module: "general" | "job_search" }) {
  const isJob = module === "job_search";
  return <ThreadPrimitive.Root className="thread-root">
    <ThreadPrimitive.Viewport className="thread-viewport">
      <AuiIf condition={(state) => state.thread.isEmpty}>
        <section className="welcome">
          <div className="welcome-logo">F</div><p className="eyebrow">FEI ASSISTANT</p>
          <h2>{isJob ? "把求职过程变成可追溯的工作流" : "今天想先处理什么？"}</h2>
          <p className="welcome-copy">{isJob ? "这里负责求职对话；岗位、投递、邮件和面试数据请在工作区管理。" : "Fei 会处理通用请求，并在任务明确涉及求职时自动调用求职模块。"}</p>
          {isJob && <div className="capability-grid">{jobCapabilities.map(([icon, title, text]) => <article className="capability-card" key={title}><span>{icon}</span><div><strong>{title}</strong><p>{text}</p></div></article>)}</div>}
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
