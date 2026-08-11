import { useEffect, useState, useCallback, useMemo } from "react";
import {
  Users,
  TrendingUp,
  TrendingDown,
  Copy,
  UserPlus,
  UserMinus,
  Award,
  X,
  Radio,
  Star,
} from "lucide-react";
import { cn } from "../lib/utils";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Input";
import { Table, Th, Td, Tr } from "../components/ui/Table";
import { Badge } from "../components/ui/Badge";
import { toast } from "../components/ui/Toast";
import { CryptoIcon } from "../components/CryptoIcon";
import { useBrokerContext } from "../context/BrokerContext";
import { isBrokerConnected } from "../lib/brokerTypes";
import { useWebSocket } from "../hooks/useWebSocket";
import * as socialApi from "../lib/socialApi";
import type { SocialLeader, SocialSignal } from "../lib/socialApi";
import { fmt } from "../lib/utils";

type Tab = "feed" | "leaders" | "myFollows" | "myCopies" | "beLeader" | "publish";

export function SocialPage() {
  const [tab, setTab] = useState<Tab>("feed");
  const [leaders, setLeaders] = useState<SocialLeader[]>([]);
  const [signals, setSignals] = useState<SocialSignal[]>([]);
  const [myFollows, setMyFollows] = useState<any[]>([]);
  const [myCopyTrades, setMyCopyTrades] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [copySignal, setCopySignal] = useState<SocialSignal | null>(null);
  const [myLeaderProfile, setMyLeaderProfile] = useState<SocialLeader | null>(null);

  // WebSocket for real-time signals
  const { connected: wsConnected } = useWebSocket("/api/social/ws/feed", {
    onMessage: (data) => {
      if (data.type === "signal" && data.signal && data.leader) {
        setSignals((prev) => {
          // Avoid duplicates
          if (prev.some((s) => s.id === data.signal.id)) return prev;
          return [{ ...data.signal, leader: data.leader }, ...prev].slice(0, 100);
        });
      }
    },
  });

  const loadLeaders = useCallback(async () => {
    try {
      const r = await socialApi.getLeaders("roi_30d", 50);
      setLeaders(r);
    } catch {}
  }, []);

  const loadSignals = useCallback(async () => {
    try {
      const r = await socialApi.getSignalsFeed("active", 50, 0);
      setSignals(r.signals);
    } catch {}
  }, []);

  const loadMyFollows = useCallback(async () => {
    try {
      const r = await socialApi.getMyFollows();
      setMyFollows(r);
    } catch {}
  }, []);

  const loadMyCopies = useCallback(async () => {
    try {
      const r = await socialApi.getMyCopyTrades();
      setMyCopyTrades(r);
    } catch {}
  }, []);

  const loadMyLeaderProfile = useCallback(async () => {
    try {
      const r = await socialApi.getMyLeaderProfile();
      setMyLeaderProfile(r);
    } catch {}
  }, []);

  useEffect(() => {
    Promise.all([loadLeaders(), loadSignals(), loadMyFollows(), loadMyCopies(), loadMyLeaderProfile()]).finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Users size={20} className="text-[var(--color-primary)]" />
          <h2 className="text-[16px] font-bold text-[var(--color-text)]">Social Trading</h2>
          <div className="flex items-center gap-1.5 ml-2">
            <span className={cn("w-2 h-2 rounded-full", wsConnected ? "bg-[var(--color-success)] animate-pulse" : "bg-[var(--color-danger)]")} />
            <span className="text-[10px] font-bold text-[var(--color-text-muted)]">
              {wsConnected ? "LIVE" : "Conectando..."}
            </span>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 rounded-[8px] bg-[var(--color-surface-2)] p-0.5">
          {[
            { id: "feed", label: "Signal Feed", icon: <Radio size={13} /> },
            { id: "leaders", label: "Líderes", icon: <Award size={13} /> },
            { id: "myFollows", label: "Mis Follows", icon: <UserPlus size={13} /> },
            { id: "myCopies", label: "Mis Copies", icon: <Copy size={13} /> },
            { id: "beLeader", label: "Ser Líder", icon: <Star size={13} /> },
            ...(myLeaderProfile ? [{ id: "publish", label: "Publicar", icon: <TrendingUp size={13} /> }] : []),
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id as Tab)}
              className={cn(
                "px-3 h-7 rounded-[6px] text-[11px] font-bold transition-colors flex items-center gap-1.5",
                tab === t.id
                  ? "bg-[var(--color-primary)] text-white"
                  : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
              )}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="text-center py-20 text-[var(--color-text-muted)] text-[13px]">Cargando...</div>
      ) : tab === "feed" ? (
        <SignalFeed signals={signals} onCopy={setCopySignal} />
      ) : tab === "leaders" ? (
        <Leaderboard leaders={leaders} onFollow={loadMyFollows} />
      ) : tab === "myFollows" ? (
        <MyFollows follows={myFollows} onUpdate={loadMyFollows} />
      ) : tab === "myCopies" ? (
        <MyCopies trades={myCopyTrades} />
      ) : tab === "beLeader" ? (
        <BecomeLeader onRegistered={() => { loadMyLeaderProfile(); }} />
      ) : tab === "publish" ? (
        <PublishSignal onPublished={() => { loadSignals(); }} />
      ) : (
        <MyCopies trades={myCopyTrades} />
      )}

      {/* Copy Modal */}
      {copySignal && (
        <CopyModal signal={copySignal} onClose={() => setCopySignal(null)} onCopied={() => { loadMyCopies(); setCopySignal(null); }} />
      )}
    </div>
  );
}

// ─── Signal Feed ─────────────────────────────────────────────────────────────

function SignalFeed({ signals, onCopy }: { signals: SocialSignal[]; onCopy: (s: SocialSignal) => void }) {
  if (signals.length === 0) {
    return (
      <Card>
        <div className="text-center py-16">
          <Radio size={32} className="mx-auto text-[var(--color-text-muted)] opacity-50" />
          <p className="text-[13px] text-[var(--color-text-muted)] mt-3">No hay señales activas</p>
          <p className="text-[11px] text-[var(--color-text-muted)] mt-1">Las nuevas señales aparecerán aquí en tiempo real</p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-2">
      {signals.map((s) => (
        <SignalCard key={s.id} signal={s} onCopy={() => onCopy(s)} />
      ))}
    </div>
  );
}

function SignalCard({ signal, onCopy }: { signal: SocialSignal; onCopy: () => void }) {
  const isBuy = signal.side === "BUY";
  const isSell = signal.side === "SELL";
  const isClosed = signal.status !== "active";

  return (
    <Card className="!p-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          {/* Leader info */}
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-[var(--color-primary)]/20 flex items-center justify-center text-[11px] font-bold text-[var(--color-primary)]">
              {signal.leader?.display_name?.charAt(0).toUpperCase() || "?"}
            </div>
            <div>
              <div className="text-[11px] font-bold text-[var(--color-text)]">{signal.leader?.display_name || "Unknown"}</div>
              <div className="text-[9px] text-[var(--color-text-muted)]">
                {signal.leader?.broker_id || "?"} · WR {signal.leader?.win_rate?.toFixed(0) || 0}%
              </div>
            </div>
          </div>

          {/* Signal info */}
          <div className="flex items-center gap-2">
            <CryptoIcon symbol={signal.symbol} size={20} />
            <div>
              <div className="text-[12px] font-bold text-[var(--color-text)]">{signal.symbol}</div>
              <div className="text-[9px] text-[var(--color-text-muted)]">
                {new Date(signal.created_at).toLocaleString("es-ES", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })}
              </div>
            </div>
          </div>
        </div>

        {/* Side badge */}
        <div className="flex items-center gap-2">
          <Badge variant={isBuy ? "success" : isSell ? "danger" : "default"}>
            {isBuy ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
            {signal.side}
          </Badge>
          <span className="text-[10px] text-[var(--color-text-muted)]">{signal.size_pct}% portfolio</span>
        </div>

        {/* Prices */}
        <div className="flex items-center gap-3 text-[10px]">
          {signal.entry_price && (
            <div className="text-center">
              <div className="text-[var(--color-text-muted)]">Entry</div>
              <div className="font-bold text-[var(--color-text)]">${fmt(signal.entry_price)}</div>
            </div>
          )}
          {signal.stop_loss && (
            <div className="text-center">
              <div className="text-[var(--color-text-muted)]">SL</div>
              <div className="font-bold text-[var(--color-danger)]">${fmt(signal.stop_loss)}</div>
            </div>
          )}
          {signal.take_profit && (
            <div className="text-center">
              <div className="text-[var(--color-text-muted)]">TP</div>
              <div className="font-bold text-[var(--color-success)]">${fmt(signal.take_profit)}</div>
            </div>
          )}
        </div>

        {/* Action */}
        {!isClosed ? (
          <Button variant="primary" size="sm" onClick={onCopy} className="!h-7 !text-[10px]">
            <Copy size={11} /> Copiar
          </Button>
        ) : (
          <Badge variant={signal.pnl_pct >= 0 ? "success" : "danger"}>
            {signal.pnl_pct >= 0 ? "+" : ""}{signal.pnl_pct.toFixed(2)}%
          </Badge>
        )}
      </div>
      {signal.comment && (
        <div className="text-[10px] text-[var(--color-text-muted)] mt-2 italic">"{signal.comment}"</div>
      )}
    </Card>
  );
}

// ─── Leaderboard ─────────────────────────────────────────────────────────────

function Leaderboard({ leaders, onFollow }: { leaders: SocialLeader[]; onFollow: () => void }) {
  const [followLoading, setFollowLoading] = useState<number | null>(null);

  const handleFollow = async (leaderId: number) => {
    setFollowLoading(leaderId);
    try {
      await socialApi.followLeader({ leader_id: leaderId });
      toast("Siguiendo al líder");
      onFollow();
    } catch (e: any) {
      toast(e.message || "Error al seguir", false);
    } finally {
      setFollowLoading(null);
    }
  };

  if (leaders.length === 0) {
    return (
      <Card>
        <div className="text-center py-16">
          <Award size={32} className="mx-auto text-[var(--color-text-muted)] opacity-50" />
          <p className="text-[13px] text-[var(--color-text-muted)] mt-3">No hay líderes registrados todavía</p>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <Table>
        <thead>
          <Tr>
            <Th>#</Th>
            <Th>Líder</Th>
            <Th>Broker</Th>
            <Th>ROI 30d</Th>
            <Th>Win Rate</Th>
            <Th>Trades</Th>
            <Th>Followers</Th>
            <Th>Acción</Th>
          </Tr>
        </thead>
        <tbody>
          {leaders.map((l, i) => (
            <Tr key={l.id}>
              <Td className="font-bold text-[var(--color-primary)]">#{i + 1}</Td>
              <Td>
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-full bg-[var(--color-primary)]/20 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)]">
                    {l.display_name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="text-[11px] font-bold text-[var(--color-text)]">{l.display_name}</div>
                    <div className="text-[9px] text-[var(--color-text-muted)]">{l.bio?.slice(0, 40)}</div>
                  </div>
                </div>
              </Td>
              <Td><span className="text-[10px] font-bold uppercase">{l.broker_id}</span></Td>
              <Td className={cn("font-bold", (l.roi_30d || 0) >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                {(l.roi_30d || 0) >= 0 ? "+" : ""}{(l.roi_30d || 0).toFixed(1)}%
              </Td>
              <Td className="font-bold">{(l.win_rate || 0).toFixed(0)}%</Td>
              <Td>{l.total_trades || 0}</Td>
              <Td className="flex items-center gap-1"><Users size={11} /> {l.total_followers || 0}</Td>
              <Td>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => handleFollow(l.id)}
                  disabled={followLoading === l.id}
                  className="!h-7 !text-[10px]"
                >
                  <UserPlus size={11} /> Seguir
                </Button>
              </Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

// ─── My Follows ─────────────────────────────────────────────────────────────

function MyFollows({ follows, onUpdate }: { follows: any[]; onUpdate: () => void }) {
  const [updating, setUpdating] = useState<number | null>(null);

  const handleUnfollow = async (followId: number) => {
    if (!confirm("¿Dejar de seguir a este líder?")) return;
    setUpdating(followId);
    try {
      await socialApi.unfollowLeader(followId);
      toast("Dejaste de seguir al líder");
      onUpdate();
    } catch (e: any) {
      toast(e.message, false);
    } finally {
      setUpdating(null);
    }
  };

  const toggleAutoCopy = async (follow: any) => {
    setUpdating(follow.id);
    try {
      await socialApi.updateFollow(follow.id, { auto_copy: !follow.auto_copy });
      toast(`Auto-copy ${!follow.auto_copy ? "activado" : "desactivado"}`);
      onUpdate();
    } catch (e: any) {
      toast(e.message, false);
    } finally {
      setUpdating(null);
    }
  };

  if (follows.length === 0) {
    return (
      <Card>
        <div className="text-center py-16">
          <UserPlus size={32} className="mx-auto text-[var(--color-text-muted)] opacity-50" />
          <p className="text-[13px] text-[var(--color-text-muted)] mt-3">No sigues a ningún líder</p>
          <p className="text-[11px] text-[var(--color-text-muted)] mt-1">Ve a la pestaña "Líderes" para empezar</p>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <Table>
        <thead>
          <Tr>
            <Th>Líder ID</Th>
            <Th>Auto-Copy</Th>
            <Th>Copy %</Th>
            <Th>Max Positions</Th>
            <Th>Max Drawdown</Th>
            <Th>Symbol Filter</Th>
            <Th>Acción</Th>
          </Tr>
        </thead>
        <tbody>
          {follows.map((f) => (
            <Tr key={f.id}>
              <Td className="font-bold">#{f.leader_id}</Td>
              <Td>
                <button
                  onClick={() => toggleAutoCopy(f)}
                  disabled={updating === f.id}
                  className={cn(
                    "px-2 h-5 rounded-[4px] text-[9px] font-bold transition-colors",
                    f.auto_copy
                      ? "bg-[var(--color-success)] text-white"
                      : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                  )}
                >
                  {f.auto_copy ? "ON" : "OFF"}
                </button>
              </Td>
              <Td>{f.copy_pct}%</Td>
              <Td>{f.max_positions}</Td>
              <Td>{f.max_drawdown_pct}%</Td>
              <Td className="text-[10px]">{f.symbol_filter || "Todos"}</Td>
              <Td>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => handleUnfollow(f.id)}
                  disabled={updating === f.id}
                  className="!h-7 !text-[10px]"
                >
                  <UserMinus size={11} /> Dejar
                </Button>
              </Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

// ─── My Copies ──────────────────────────────────────────────────────────────

function MyCopies({ trades }: { trades: any[] }) {
  if (trades.length === 0) {
    return (
      <Card>
        <div className="text-center py-16">
          <Copy size={32} className="mx-auto text-[var(--color-text-muted)] opacity-50" />
          <p className="text-[13px] text-[var(--color-text-muted)] mt-3">No has copiado ninguna señal</p>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <Table>
        <thead>
          <Tr>
            <Th>Fecha</Th>
            <Th>Símbolo</Th>
            <Th>Side</Th>
            <Th>Broker</Th>
            <Th>Size USD</Th>
            <Th>Entry</Th>
            <Th>Estado</Th>
            <Th>PNL</Th>
          </Tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <Tr key={t.id}>
              <Td className="text-[10px]">{new Date(t.created_at).toLocaleString("es-ES", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })}</Td>
              <Td className="font-bold">{t.symbol}</Td>
              <Td><Badge variant={t.side === "BUY" ? "success" : "danger"}>{t.side}</Badge></Td>
              <Td className="text-[10px] uppercase">{t.broker_id}</Td>
              <Td>${fmt(t.size_usd)}</Td>
              <Td>{t.entry_price ? `$${fmt(t.entry_price)}` : "-"}</Td>
              <Td>
                <Badge variant={t.status === "executed" ? "success" : t.status === "failed" ? "danger" : "default"}>
                  {t.status}
                </Badge>
              </Td>
              <Td className={cn("font-bold", t.pnl >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                {t.pnl >= 0 ? "+" : ""}${fmt(t.pnl)}
              </Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

// ─── Copy Modal ──────────────────────────────────────────────────────────────

function CopyModal({ signal, onClose, onCopied }: { signal: SocialSignal; onClose: () => void; onCopied: () => void }) {
  const { connectedAccounts } = useBrokerContext();
  const connectedBrokers = useMemo(
    () => connectedAccounts.filter((a) => isBrokerConnected(a.status)),
    [connectedAccounts]
  );

  const [brokerId, setBrokerId] = useState(connectedBrokers[0]?.brokerId || "");
  const [sizeUsd, setSizeUsd] = useState("");
  const [loading, setLoading] = useState(false);

  const handleCopy = async () => {
    if (!brokerId) {
      toast("Selecciona un broker", false);
      return;
    }
    setLoading(true);
    try {
      const result = await socialApi.copySignal(signal.id, {
        broker_id: brokerId,
        size_usd: sizeUsd ? parseFloat(sizeUsd) : undefined,
      });
      toast(`Copiado: ${result.symbol} ${result.side} $${fmt(result.size_usd)} en ${result.broker}`);
      onCopied();
    } catch (e: any) {
      toast(e.message || "Error al copiar señal", false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="panel w-[400px] max-w-[90vw] p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Copiar Señal</h3>
          <button onClick={onClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X size={18} />
          </button>
        </div>

        {/* Signal summary */}
        <div className="rounded-[10px] bg-[var(--color-surface-2)] p-3 mb-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <CryptoIcon symbol={signal.symbol} size={20} />
              <span className="text-[13px] font-bold">{signal.symbol}</span>
            </div>
            <Badge variant={signal.side === "BUY" ? "success" : "danger"}>{signal.side}</Badge>
          </div>
          <div className="grid grid-cols-3 gap-2 text-[10px]">
            {signal.entry_price && (
              <div><div className="text-[var(--color-text-muted)]">Entry</div><div className="font-bold">${fmt(signal.entry_price)}</div></div>
            )}
            {signal.stop_loss && (
              <div><div className="text-[var(--color-text-muted)]">SL</div><div className="font-bold text-red-400">${fmt(signal.stop_loss)}</div></div>
            )}
            {signal.take_profit && (
              <div><div className="text-[var(--color-text-muted)]">TP</div><div className="font-bold text-green-400">${fmt(signal.take_profit)}</div></div>
            )}
          </div>
        </div>

        {/* Broker selector */}
        <div className="mb-3">
          <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">Tu Broker</label>
          {connectedBrokers.length === 0 ? (
            <div className="text-[11px] text-[var(--color-danger)] py-2">
              No tienes brokers conectados. Conecta uno en la pestaña Conexiones.
            </div>
          ) : (
            <Select value={brokerId} onChange={(e) => setBrokerId(e.target.value)}>
              {connectedBrokers.map((b) => (
                <option key={b.brokerId} value={b.brokerId}>
                  {b.brokerId} {b.environment === "testnet" ? "(testnet)" : ""}
                </option>
              ))}
            </Select>
          )}
        </div>

        {/* Size input */}
        <div className="mb-4">
          <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">
            Tamaño USD (opcional)
          </label>
          <Input
            type="number"
            value={sizeUsd}
            onChange={(e) => setSizeUsd(e.target.value)}
            placeholder="Auto (basado en tu config de follow)"
            min="0"
            step="10"
          />
          <div className="text-[9px] text-[var(--color-text-muted)] mt-1">
            Si lo dejas vacío, se usará el % configurado en tu follow
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <Button variant="default" size="sm" onClick={onClose} className="flex-1">Cancelar</Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleCopy}
            disabled={loading || !brokerId || connectedBrokers.length === 0}
            className="flex-1"
          >
            {loading ? "Ejecutando..." : "Copiar Trade"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Become Leader ───────────────────────────────────────────────────────────

function BecomeLeader({ onRegistered }: { onRegistered: () => void }) {
  const { connectedAccounts } = useBrokerContext();
  const connectedBrokers = useMemo(
    () => connectedAccounts.filter((a) => isBrokerConnected(a.status)),
    [connectedAccounts]
  );
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [brokerId, setBrokerId] = useState(connectedBrokers[0]?.brokerId || "binance");
  const [isPublic, setIsPublic] = useState(true);
  const [loading, setLoading] = useState(false);
  const [existingProfile, setExistingProfile] = useState<SocialLeader | null>(null);

  useEffect(() => {
    socialApi.getMyLeaderProfile().then((r) => setExistingProfile(r || null)).catch(() => {});
  }, []);

  const handleRegister = async () => {
    if (!displayName.trim()) {
      toast("Ingresa tu nombre público", false);
      return;
    }
    setLoading(true);
    try {
      await socialApi.registerLeader({
        display_name: displayName,
        bio,
        broker_id: brokerId,
        is_public: isPublic,
      });
      toast("¡Ahora eres líder! Ya puedes publicar señales");
      onRegistered();
      socialApi.getMyLeaderProfile().then((r) => setExistingProfile(r || null));
    } catch (e: any) {
      toast(e.message || "Error al registrarse", false);
    } finally {
      setLoading(false);
    }
  };

  if (existingProfile) {
    return (
      <Card>
        <div className="p-5">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-full bg-[var(--color-primary)]/20 flex items-center justify-center text-[16px] font-bold text-[var(--color-primary)]">
              {existingProfile.display_name.charAt(0).toUpperCase()}
            </div>
            <div>
              <h3 className="text-[14px] font-bold text-[var(--color-text)]">{existingProfile.display_name}</h3>
              <p className="text-[11px] text-[var(--color-text-muted)]">{existingProfile.bio || "Sin bio"}</p>
            </div>
            <Badge variant="success" className="ml-auto"><Star size={10} /> Líder</Badge>
          </div>

          <div className="grid grid-cols-4 gap-3 mb-4">
            <StatBox label="ROI 30d" value={`${(existingProfile.roi_30d || 0).toFixed(1)}%`} positive={(existingProfile.roi_30d || 0) >= 0} />
            <StatBox label="Win Rate" value={`${(existingProfile.win_rate || 0).toFixed(0)}%`} />
            <StatBox label="Trades" value={`${existingProfile.total_trades || 0}`} />
            <StatBox label="Followers" value={`${existingProfile.total_followers || 0}`} />
          </div>

          <div className="text-[11px] text-[var(--color-text-muted)] mb-3">
            Broker: <span className="font-bold uppercase">{existingProfile.broker_id}</span> ·
            Público: {existingProfile.is_public ? "Sí" : "No"}
          </div>

          <p className="text-[11px] text-[var(--color-text-muted)]">
            Ve a la pestaña <span className="font-bold text-[var(--color-primary)]">"Publicar"</span> para crear nuevas señales.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="p-5 max-w-md">
        <h3 className="text-[14px] font-bold text-[var(--color-text)] mb-2">Convertirse en Líder</h3>
        <p className="text-[11px] text-[var(--color-text-muted)] mb-4">
          Publica señales de trading para que otros usuarios puedan copiarlas en sus brokers.
        </p>

        <div className="space-y-3">
          <div>
            <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">Nombre público</label>
            <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="ej: CryptoWhale" />
          </div>

          <div>
            <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">Bio (opcional)</label>
            <Input value={bio} onChange={(e) => setBio(e.target.value)} placeholder="ej: Swing trader, 5 años de experiencia" />
          </div>

          <div>
            <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">Tu broker principal</label>
            <Select value={brokerId} onChange={(e) => setBrokerId(e.target.value)}>
              {connectedBrokers.length > 0 ? (
                connectedBrokers.map((b) => (
                  <option key={b.brokerId} value={b.brokerId}>{b.brokerId}</option>
                ))
              ) : (
                <option value="binance">binance</option>
              )}
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={isPublic}
              onChange={(e) => setIsPublic(e.target.checked)}
              className="w-4 h-4 rounded accent-[var(--color-primary)]"
            />
            <label className="text-[11px] text-[var(--color-text)]">Perfil público (otros usuarios pueden verte)</label>
          </div>

          <Button variant="primary" onClick={handleRegister} disabled={loading || !displayName.trim()} className="w-full">
            {loading ? "Registrando..." : "Registrarse como Líder"}
          </Button>
        </div>
      </div>
    </Card>
  );
}

// ─── Publish Signal ──────────────────────────────────────────────────────────

function PublishSignal({ onPublished }: { onPublished: () => void }) {
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [sizePct, setSizePct] = useState("5");
  const [entryPrice, setEntryPrice] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);

  const handlePublish = async () => {
    if (!symbol.trim()) {
      toast("Ingresa un símbolo (ej: BTCUSDT)", false);
      return;
    }
    setLoading(true);
    try {
      await socialApi.publishSignal({
        symbol: symbol.toUpperCase(),
        side,
        size_pct: parseFloat(sizePct) || 5,
        entry_price: entryPrice ? parseFloat(entryPrice) : undefined,
        stop_loss: stopLoss ? parseFloat(stopLoss) : undefined,
        take_profit: takeProfit ? parseFloat(takeProfit) : undefined,
        comment,
      });
      toast("Señal publicada");
      setSymbol(""); setEntryPrice(""); setStopLoss(""); setTakeProfit(""); setComment("");
      onPublished();
    } catch (e: any) {
      toast(e.message || "Error al publicar", false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <div className="p-5 max-w-md">
        <h3 className="text-[14px] font-bold text-[var(--color-text)] mb-4">Publicar Señal</h3>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">Símbolo</label>
              <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="BTCUSDT" />
            </div>
            <div>
              <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">Side</label>
              <Select value={side} onChange={(e) => setSide(e.target.value as "BUY" | "SELL")}>
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </Select>
            </div>
          </div>

          <div>
            <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">% del portfolio</label>
            <Input type="number" value={sizePct} onChange={(e) => setSizePct(e.target.value)} min="0.1" step="0.5" />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">Entry</label>
              <Input type="number" value={entryPrice} onChange={(e) => setEntryPrice(e.target.value)} placeholder="Auto" />
            </div>
            <div>
              <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">SL</label>
              <Input type="number" value={stopLoss} onChange={(e) => setStopLoss(e.target.value)} placeholder="Opcional" />
            </div>
            <div>
              <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">TP</label>
              <Input type="number" value={takeProfit} onChange={(e) => setTakeProfit(e.target.value)} placeholder="Opcional" />
            </div>
          </div>

          <div>
            <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">Comentario</label>
            <Input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="ej: Breakout de resistencia" />
          </div>

          <Button variant="primary" onClick={handlePublish} disabled={loading || !symbol.trim()} className="w-full">
            {loading ? "Publicando..." : "Publicar Señal"}
          </Button>
        </div>
      </div>
    </Card>
  );
}

// ─── Stat Box ────────────────────────────────────────────────────────────────

function StatBox({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div className="rounded-[8px] bg-[var(--color-surface-2)] p-2 text-center">
      <div className="text-[9px] text-[var(--color-text-muted)] uppercase">{label}</div>
      <div className={cn("text-[13px] font-bold", positive === true ? "text-[var(--color-success)]" : positive === false ? "text-[var(--color-danger)]" : "text-[var(--color-text)]")}>
        {value}
      </div>
    </div>
  );
}
