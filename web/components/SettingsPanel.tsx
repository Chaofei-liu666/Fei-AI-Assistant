"use client";

import { FormEvent, useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";

type Provider = { slot: string; provider: string; base_url?: string; model?: string; config: Record<string, unknown>; configured: boolean; secret_last_four?: string };

export function SettingsPanel() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [notice, setNotice] = useState("");
  const refresh = () => api<Provider[]>("/api/settings/providers").then(setProviders).catch((e) => setNotice(e.message));
  useEffect(() => { void refresh(); }, []);
  const current = (slot: string) => providers.find((p) => p.slot === slot);
  const save = async (event: FormEvent<HTMLFormElement>, slot: string, provider: string) => {
    event.preventDefault(); const values = Object.fromEntries(new FormData(event.currentTarget));
    const config: Record<string, unknown> = {}; const secrets: Record<string, string> = {};
    for (const key of ["username","host","port","dashscope_workspace_id","dashscope_region_domain","oss_access_key_id","oss_endpoint","oss_bucket"]) if (values[key]) config[key] = values[key];
    if (values.oss_secret) secrets.oss_secret = String(values.oss_secret);
    const payload = { slot, provider: String(values.provider || provider), base_url: values.base_url || null, model: values.model || null, secret: values.secret || null, secrets, config };
    try { await api(`/api/settings/providers/${slot}`, { method: "PUT", body: JSON.stringify(payload) }); setNotice("配置已保存到系统凭据库"); refresh(); } catch (error) { setNotice(error instanceof Error ? error.message : "保存失败"); }
  };
  return <div className="workspace-scroll settings"><div className="workspace-heading"><div><h2>设置</h2><p>所有 Agent 继承全局文本模型；语音与邮箱凭据独立配置。</p></div></div>{notice && <div className="notice">{notice}</div>}
    <ProviderForm title="全局文本模型" slot="text" provider={current("text")?.provider || "deepseek"} saved={current("text")} onSubmit={save}>
      <select name="provider" defaultValue={current("text")?.provider || "deepseek"}><option value="deepseek">DeepSeek 预设</option><option value="openai_compatible">自定义 OpenAI-compatible</option></select><input name="base_url" placeholder="Base URL（DeepSeek 可留空）" defaultValue={current("text")?.base_url} /><input name="model" placeholder="模型名，例如 deepseek-chat" defaultValue={current("text")?.model} required /><input name="secret" type="password" placeholder={current("text")?.configured ? `API Key 已保存 ····${current("text")?.secret_last_four}` : "API Key"} />
    </ProviderForm>
    <ProviderForm title="阿里云 Paraformer" slot="speech" provider="aliyun_paraformer" saved={current("speech")} onSubmit={save}>
      <input name="model" defaultValue={current("speech")?.model || "paraformer-v2"} /><input name="secret" type="password" placeholder={current("speech")?.configured ? `DashScope Key 已保存 ····${current("speech")?.secret_last_four}` : "DashScope API Key"} /><input name="dashscope_workspace_id" placeholder="DashScope Workspace ID" defaultValue={String(current("speech")?.config.dashscope_workspace_id ?? "")} /><input name="dashscope_region_domain" placeholder="地域域名" defaultValue={String(current("speech")?.config.dashscope_region_domain ?? "cn-beijing.maas.aliyuncs.com")} /><input name="oss_access_key_id" placeholder="OSS AccessKey ID" defaultValue={String(current("speech")?.config.oss_access_key_id ?? "")} /><input name="oss_secret" type="password" placeholder="OSS AccessKey Secret（留空则不变）" /><input name="oss_endpoint" placeholder="OSS Endpoint" defaultValue={String(current("speech")?.config.oss_endpoint ?? "")} /><input name="oss_bucket" placeholder="私有 OSS Bucket" defaultValue={String(current("speech")?.config.oss_bucket ?? "")} />
    </ProviderForm>
    <ProviderForm title="163 邮箱（只读）" slot="email" provider="email_163" saved={current("email")} onSubmit={save}>
      <input name="username" type="email" placeholder="邮箱地址" defaultValue={String(current("email")?.config.username ?? "")} required /><input name="secret" type="password" placeholder={current("email")?.configured ? `授权码已保存 ····${current("email")?.secret_last_four}` : "客户端授权码"} /><input name="host" defaultValue={String(current("email")?.config.host ?? "imap.163.com")} /><input name="port" defaultValue={String(current("email")?.config.port ?? "993")} />
    </ProviderForm>
    <section className="workspace-card"><h3>环境变量管理</h3><p>PostgreSQL 与 MinIO 连接信息只从主机环境变量读取，不通过浏览器保存或展示。</p></section>
  </div>;
}

function ProviderForm({ title, slot, provider, saved, onSubmit, children }: { title: string; slot: string; provider: string; saved?: Provider; onSubmit: (event: FormEvent<HTMLFormElement>, slot: string, provider: string) => void; children: ReactNode }) {
  return <form className="workspace-card settings-form" onSubmit={(e) => onSubmit(e, slot, provider)}><div><h3>{title}</h3><span className={`status-pill ${saved?.configured ? "ready" : ""}`}>{saved?.configured ? "已配置" : "未配置"}</span></div><div className="form-grid">{children}</div><div className="record-actions"><button className="primary" type="submit">保存配置</button>{saved?.configured && <button type="button" onClick={() => fetch(`${process.env.NEXT_PUBLIC_FEI_API_URL ?? "http://127.0.0.1:8000"}/api/settings/providers/${slot}/test`, { method: "POST" }).then(async r => { if (!r.ok) throw new Error((await r.json()).detail); return r.json(); }).then(result => alert(`能力测试结果：${JSON.stringify(result)}`)).catch(error => alert(error.message))}>连接与能力测试</button>}</div></form>;
}
