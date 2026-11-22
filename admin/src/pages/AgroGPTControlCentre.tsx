import React, { useEffect, useState } from 'react';
import { adminFetch } from '../lib/api';
import { Bot, RefreshCw, ShieldAlert, CheckCircle2, XCircle, Activity, MessageSquare } from 'lucide-react';

interface ControlCentreData {
  checked_at: string;
  providers_configured: Record<string, boolean>;
  task_routing: Record<string, string>;
  model_registry: Array<{
    key: string;
    provider: string;
    model: string;
    capabilities: string[];
    context_window: number;
    cost_tier: string;
    fallbacks: string[];
    eval_scores: Record<string, number>;
  }>;
  telemetry: {
    total_calls: number;
    calls_24h: number;
    avg_latency_ms: number | null;
    estimated_cost_usd: number;
    by_tier: Record<string, number>;
    by_task: Record<string, number>;
    guard_flags: Record<string, number>;
    recent: Array<{
      id: string;
      request_id: string;
      task_category: string | null;
      provider: string | null;
      model: string | null;
      source_tier: string;
      guard_flags: string[];
      latency_ms: number | null;
      created_at: string | null;
    }>;
  };
  feedback: {
    total: number;
    helpful: number;
    not_helpful: number;
    recent: Array<{
      id: string;
      message_id: string;
      rating: string;
      reason_tag: string | null;
      comment: string | null;
      created_at: string | null;
    }>;
  };
  baseline_eval: {
    version?: string;
    tiers?: Record<string, number>;
    auto_pass_summary?: Record<string, string>;
    caveat?: string;
  } | null;
}

export const AgroGPTControlCentre: React.FC = () => {
  const [data, setData] = useState<ControlCentreData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/agrogpt/control-centre');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e: any) {
      setError(e.message || 'Failed to load AgroGPT telemetry');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading && !data) {
    return <div className="p-8 text-sm text-[#4B5563]">Loading AgroGPT Control Centre...</div>;
  }

  if (error && !data) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
        Could not load AgroGPT Control Centre: {error}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-[#081C15] flex items-center gap-2">
            <Bot size={22} className="text-[#2D6A4F]" /> AgroGPT Control Centre
          </h2>
          <p className="text-xs text-[#6B7280] mt-0.5">
            Live model registry, routing, deterministic safety guard telemetry & farmer feedback · Never exposes API keys
          </p>
        </div>
        <button
          onClick={load}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-[#1B4332] text-white text-xs font-semibold hover:bg-[#2D6A4F] transition cursor-pointer"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {/* Top KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-4">
          <div className="text-xs text-[#6B7280] font-medium">Total Recorded Calls</div>
          <div className="text-2xl font-bold text-[#081C15] mt-1">{data.telemetry.total_calls}</div>
          <div className="text-[11px] text-[#2D6A4F] mt-1">{data.telemetry.calls_24h} in last 24h</div>
        </div>
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-4">
          <div className="text-xs text-[#6B7280] font-medium">Average Latency</div>
          <div className="text-2xl font-bold text-[#081C15] mt-1">
            {data.telemetry.avg_latency_ms !== null ? `${data.telemetry.avg_latency_ms} ms` : '—'}
          </div>
          <div className="text-[11px] text-[#6B7280] mt-1">Measured server-side</div>
        </div>
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-4">
          <div className="text-xs text-[#6B7280] font-medium">Safety Guard Triggers</div>
          <div className="text-2xl font-bold text-[#081C15] mt-1">
            {Object.values(data.telemetry.guard_flags).reduce((a, b) => a + b, 0)}
          </div>
          <div className="text-[11px] text-[#6B7280] mt-1">
            {Object.keys(data.telemetry.guard_flags).length > 0
              ? Object.entries(data.telemetry.guard_flags).map(([k, v]) => `${k}: ${v}`).join(' · ')
              : 'No guard triggers recorded yet'}
          </div>
        </div>
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-4">
          <div className="text-xs text-[#6B7280] font-medium">Farmer Feedback</div>
          <div className="text-2xl font-bold text-[#081C15] mt-1">{data.feedback.total}</div>
          <div className="text-[11px] text-[#6B7280] mt-1">
            {data.feedback.helpful} helpful · {data.feedback.not_helpful} not helpful
          </div>
        </div>
      </div>

      {/* Provider Configuration (booleans only) + Task Routing */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5">
          <h3 className="text-sm font-bold text-[#081C15] mb-3 flex items-center gap-2">
            <Activity size={16} className="text-[#2D6A4F]" /> Provider Credentials Status
          </h3>
          <div className="space-y-2.5">
            {Object.entries(data.providers_configured).map(([prov, ok]) => (
              <div key={prov} className="flex items-center justify-between py-2 px-3 rounded-xl bg-[#FAF8F5] border border-[#E5E7EB]">
                <span className="text-sm font-semibold capitalize text-[#1F2937]">{prov}</span>
                {ok ? (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#1B4332] bg-[#D1FAE5] px-2.5 py-0.5 rounded-full">
                    <CheckCircle2 size={13} /> Configured (Server Env)
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#92400E] bg-[#FEF3C7] px-2.5 py-0.5 rounded-full">
                    <XCircle size={13} /> Not Configured
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5">
          <h3 className="text-sm font-bold text-[#081C15] mb-3 flex items-center gap-2">
            <ShieldAlert size={16} className="text-[#2D6A4F]" /> Deterministic Task Routing
          </h3>
          <div className="grid grid-cols-2 gap-2.5">
            {Object.entries(data.task_routing).map(([task, target]) => (
              <div key={task} className="p-2.5 rounded-xl bg-[#FAF8F5] border border-[#E5E7EB]">
                <div className="text-[11px] uppercase tracking-wider font-semibold text-[#6B7280]">{task.replace('_', ' ')}</div>
                <div className="text-sm font-bold text-[#1B4332] mt-0.5">{target}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Model Registry Table */}
      <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5 overflow-x-auto">
        <h3 className="text-sm font-bold text-[#081C15] mb-3">Server-Side Model Registry</h3>
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-[#E5E7EB] text-[#6B7280] uppercase">
              <th className="py-2 pr-4">Key</th>
              <th className="py-2 pr-4">Provider</th>
              <th className="py-2 pr-4">Model ID</th>
              <th className="py-2 pr-4">Capabilities</th>
              <th className="py-2 pr-4">Context</th>
              <th className="py-2">Fallbacks</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#F3F4F6]">
            {data.model_registry.map((m) => (
              <tr key={m.key}>
                <td className="py-2.5 pr-4 font-semibold text-[#081C15]">{m.key}</td>
                <td className="py-2.5 pr-4 capitalize">{m.provider}</td>
                <td className="py-2.5 pr-4 font-mono text-[11px] text-[#1B4332]">{m.model}</td>
                <td className="py-2.5 pr-4">{m.capabilities.join(', ')}</td>
                <td className="py-2.5 pr-4">{m.context_window.toLocaleString()}</td>
                <td className="py-2.5 text-[#6B7280]">{m.fallbacks.length ? m.fallbacks.join(' → ') : 'None'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* G1 Baseline Summary (if present) */}
      {data.baseline_eval && (
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5">
          <h3 className="text-sm font-bold text-[#081C15] mb-1">G1 Evaluation Baseline ({data.baseline_eval.version})</h3>
          <p className="text-xs text-[#6B7280] mb-3">{data.baseline_eval.caveat}</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            {Object.entries(data.baseline_eval.auto_pass_summary || {}).map(([k, v]) => (
              <div key={k} className="p-2.5 rounded-xl bg-[#FAF8F5] border border-[#E5E7EB]">
                <div className="text-[11px] text-[#6B7280] font-medium">{k}</div>
                <div className="text-base font-bold text-[#081C15]">{v}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Telemetry Rows */}
      <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5 overflow-x-auto">
        <h3 className="text-sm font-bold text-[#081C15] mb-3 flex items-center gap-2">
          <MessageSquare size={15} className="text-[#2D6A4F]" /> Recent AgroGPT Requests (No Prompt PII Logged)
        </h3>
        {data.telemetry.recent.length === 0 ? (
          <p className="text-xs text-[#6B7280]">No AgroGPT requests recorded yet.</p>
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E5E7EB] text-[#6B7280] uppercase">
                <th className="py-2 pr-3">Request ID</th>
                <th className="py-2 pr-3">Task</th>
                <th className="py-2 pr-3">Tier / Model</th>
                <th className="py-2 pr-3">Latency</th>
                <th className="py-2 pr-3">Guard Flags</th>
                <th className="py-2">Time (UTC)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F3F4F6]">
              {data.telemetry.recent.map((r) => (
                <tr key={r.id}>
                  <td className="py-2 pr-3 font-mono text-[11px]">{r.request_id}</td>
                  <td className="py-2 pr-3">{r.task_category || '—'}</td>
                  <td className="py-2 pr-3">{r.source_tier} ({r.model || '—'})</td>
                  <td className="py-2 pr-3">{r.latency_ms !== null ? `${r.latency_ms} ms` : '—'}</td>
                  <td className="py-2 pr-3">{r.guard_flags.length ? r.guard_flags.join(', ') : 'clean'}</td>
                  <td className="py-2 text-[#6B7280]">{r.created_at ? r.created_at.slice(0, 19).replace('T', ' ') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
