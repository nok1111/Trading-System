// TaxStudioPage — multi-country crypto tax calculation and reporting.

import { useEffect, useState, useCallback } from "react";
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Receipt,
  Download,
  Save,
  Calculator,
  FileText,
  Loader2,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";
import { Panel } from "../components/ui/Card";
import { CountrySelector, CountryGrid } from "../components/tax/CountrySelector";
import { TaxMethodSelector } from "../components/tax/TaxMethodSelector";
import { TaxSummaryCard } from "../components/tax/TaxSummaryCard";
import {
  getTaxCountries,
  calculateTax,
  saveTaxReport,
  getTaxReports,
  downloadTaxReportCsv,
  type CountryInfo,
  type TaxReport,
  type TaxMethod,
  type SavedTaxReport,
} from "../lib/taxApi";
import { cn } from "../lib/utils";

const CURRENT_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: 6 }, (_, i) => CURRENT_YEAR - i);

const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$", EUR: "€", GBP: "£", CAD: "C$", AUD: "A$", JPY: "¥",
};

function curSym(currency: string): string {
  return CURRENCY_SYMBOLS[currency] || "$";
}

function fmtMoney(v: string | number, currency = "USD"): string {
  const n = Number(v);
  if (isNaN(n)) return "-";
  const sym = curSym(currency);
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${sign}${sym}${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}${sym}${(abs / 1_000).toFixed(2)}K`;
  return `${sign}${sym}${abs.toFixed(2)}`;
}

function fmtSigned(v: string | number, currency = "USD"): string {
  const n = Number(v);
  if (isNaN(n)) return "-";
  const sign = n >= 0 ? "+" : "-";
  return `${sign}${fmtMoney(Math.abs(n), currency)}`;
}

export function TaxStudioPage() {
  const [countries, setCountries] = useState<CountryInfo[]>([]);
  const [country, setCountry] = useState("US");
  const [year, setYear] = useState(CURRENT_YEAR);
  const [method, setMethod] = useState<TaxMethod>("fifo");
  const [report, setReport] = useState<TaxReport | null>(null);
  const [savedReports, setSavedReports] = useState<SavedTaxReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Load countries on mount
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const cs = await getTaxCountries();
        if (alive) setCountries(cs);
      } catch (e) {
        console.error("Failed to load tax countries:", e);
      }
    })();
    return () => { alive = false; };
  }, []);

  // Load saved reports
  const loadSavedReports = useCallback(async () => {
    try {
      const reports = await getTaxReports();
      setSavedReports(reports);
    } catch (e) {
      console.error("Failed to load saved reports:", e);
    }
  }, []);

  useEffect(() => {
    loadSavedReports();
  }, [loadSavedReports]);

  const handleCalculate = async () => {
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const result = await calculateTax({ year, country, method });
      setReport(result);
    } catch (e: any) {
      setError(e?.message || "Failed to calculate tax report");
      setReport(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!report) return;
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await saveTaxReport(year, country, method, report);
      setSuccessMsg("Report saved successfully");
      await loadSavedReports();
    } catch (e: any) {
      setError(e?.message || "Failed to save report");
    } finally {
      setSaving(false);
    }
  };

  const handleExportCsv = async (reportId?: number) => {
    try {
      if (reportId) {
        // Download from saved report
        const csv = await downloadTaxReportCsv(reportId);
        downloadCsvString(csv, `tax_report_${reportId}.csv`);
      } else if (report) {
        // Export current unsaved report
        const csvStr = generateCsvFromReport(report);
        downloadCsvString(csvStr, `tax_report_${country}_${year}_${method}.csv`);
      }
    } catch (e: any) {
      setError(e?.message || "Failed to export CSV");
    }
  };

  const summary = report?.summary;
  const disposals = report?.disposals ?? [];
  const currency = report?.currency || "USD";

  return (
    <div className="p-5 space-y-4 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-[20px] font-bold text-[var(--color-text)] flex items-center gap-2">
            <Receipt size={22} className="text-[var(--color-primary)]" />
            Tax Studio
          </h1>
          <p className="text-[12px] text-[var(--color-text-muted)] mt-0.5">
            Multi-country crypto tax calculation and reporting
          </p>
        </div>
      </div>

      {/* Configuration panel */}
      <Panel
        title="Tax Configuration"
        icon={<Calculator size={16} />}
        tone="primary"
      >
        <div className="space-y-4">
          {/* Country grid */}
          {countries.length > 0 && (
            <CountryGrid
              countries={countries}
              value={country}
              onChange={setCountry}
            />
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Country dropdown (alternative selection) */}
            {countries.length > 0 && (
              <CountrySelector
                countries={countries}
                value={country}
                onChange={setCountry}
              />
            )}

            {/* Year selector */}
            <div className="space-y-1.5">
              <label className="block text-[12px] font-semibold text-[var(--color-text-muted)]">
                Tax Year
              </label>
              <Select
                value={String(year)}
                onChange={(e) => setYear(Number(e.target.value))}
                className="w-full"
              >
                {YEARS.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </Select>
            </div>

            {/* Method selector */}
            <TaxMethodSelector value={method} onChange={setMethod} />
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 flex-wrap">
            <Button
              variant="primary"
              size="md"
              onClick={handleCalculate}
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Calculating...
                </>
              ) : (
                <>
                  <Calculator size={14} />
                  Calculate
                </>
              )}
            </Button>
            <Button
              variant="default"
              size="md"
              onClick={handleSave}
              disabled={!report || saving}
            >
              {saving ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save size={14} />
                  Save Report
                </>
              )}
            </Button>
            <Button
              variant="default"
              size="md"
              onClick={() => handleExportCsv()}
              disabled={!report}
            >
              <Download size={14} />
              Export CSV
            </Button>
          </div>

          {/* Messages */}
          {error && (
            <div className="text-[12px] text-[var(--color-danger)] bg-[var(--color-danger)]/10 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
          {successMsg && (
            <div className="text-[12px] text-[var(--color-success)] bg-[var(--color-success)]/10 rounded-lg px-3 py-2">
              {successMsg}
            </div>
          )}
        </div>
      </Panel>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <TaxSummaryCard
            label="Total Gains"
            value={fmtMoney(summary.total_gains, currency)}
            icon={<TrendingUp size={18} />}
            tone="success"
            sublabel={`${summary.disposal_count} disposals`}
          />
          <TaxSummaryCard
            label="Total Losses"
            value={fmtMoney(Math.abs(Number(summary.total_losses)), currency)}
            icon={<TrendingDown size={18} />}
            tone="danger"
          />
          <TaxSummaryCard
            label="Net Gain / Loss"
            value={fmtSigned(summary.net_gain, currency)}
            icon={<DollarSign size={18} />}
            tone={Number(summary.net_gain) >= 0 ? "success" : "danger"}
            sublabel={`${summary.trade_count} trades analyzed`}
          />
          <TaxSummaryCard
            label="Estimated Tax"
            value={fmtMoney(summary.estimated_tax, currency)}
            icon={<Receipt size={18} />}
            tone="warning"
            sublabel={`Taxable: ${fmtMoney(summary.taxable_gain, currency)}`}
          />
        </div>
      )}

      {/* Country-specific form info */}
      {report?.country_form && (
        <Panel
          title={report.form_name || "Tax Form"}
          icon={<FileText size={16} />}
          tone="accent"
        >
          <div className="space-y-2">
            <div className="text-[13px] font-bold text-[var(--color-text)]">
              {report.country_form.title}
            </div>
            {typeof report.country_form.notes === "string" && (
              <div className="text-[12px] text-[var(--color-text-muted)]">
                {report.country_form.notes}
              </div>
            )}
            {/* Render key-value pairs from country form */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-2">
              {Object.entries(report.country_form)
                .filter(([k]) => !["form", "title", "notes", "rows", "brackets"].includes(k))
                .map(([key, val]) => (
                  <div
                    key={key}
                    className="flex flex-col bg-[var(--color-surface-2)] rounded-lg px-3 py-2"
                  >
                    <span className="text-[10px] uppercase text-[var(--color-text-muted)] font-semibold">
                      {key.replace(/_/g, " ")}
                    </span>
                    <span className="num text-[14px] font-bold text-[var(--color-text)]">
                      {String(val)}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </Panel>
      )}

      {/* Disposals table */}
      {disposals.length > 0 && (
        <Panel
          title="Trade Disposals — P&L Breakdown"
          icon={<FileText size={16} />}
          tone="cyan"
          actions={
            <span className="text-[11px] text-[var(--color-text-muted)]">
              {disposals.length} matched lots
            </span>
          }
          bodyClassName="overflow-x-auto"
        >
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                <th className="py-2 pr-3 font-semibold">Symbol</th>
                <th className="py-2 pr-3 font-semibold">Buy Date</th>
                <th className="py-2 pr-3 font-semibold">Sell Date</th>
                <th className="py-2 pr-3 font-semibold text-right">Qty</th>
                <th className="py-2 pr-3 font-semibold text-right">Buy Price</th>
                <th className="py-2 pr-3 font-semibold text-right">Sell Price</th>
                <th className="py-2 pr-3 font-semibold text-right">Proceeds</th>
                <th className="py-2 pr-3 font-semibold text-right">Cost Basis</th>
                <th className="py-2 pr-3 font-semibold text-right">Gain/Loss</th>
                <th className="py-2 pr-3 font-semibold text-right">Hold Days</th>
                <th className="py-2 pr-3 font-semibold">Type</th>
              </tr>
            </thead>
            <tbody>
              {disposals.map((d, i) => {
                const gain = Number(d.gain);
                const isGain = gain >= 0;
                return (
                  <tr
                    key={i}
                    className="border-b border-[var(--color-border)]/50 hover:bg-[var(--color-surface-2)]/50"
                  >
                    <td className="py-2 pr-3 font-bold text-[var(--color-text)]">
                      {d.symbol}
                    </td>
                    <td className="py-2 pr-3 text-[var(--color-text-muted)]">
                      {(d.buy_timestamp || "").slice(0, 10)}
                    </td>
                    <td className="py-2 pr-3 text-[var(--color-text-muted)]">
                      {(d.sell_timestamp || "").slice(0, 10)}
                    </td>
                    <td className="py-2 pr-3 text-right num">
                      {Number(d.quantity).toFixed(6)}
                    </td>
                    <td className="py-2 pr-3 text-right num">
                      {Number(d.buy_price).toFixed(2)}
                    </td>
                    <td className="py-2 pr-3 text-right num">
                      {Number(d.sell_price).toFixed(2)}
                    </td>
                    <td className="py-2 pr-3 text-right num">
                      {Number(d.proceeds).toFixed(2)}
                    </td>
                    <td className="py-2 pr-3 text-right num">
                      {Number(d.cost_basis).toFixed(2)}
                    </td>
                    <td
                      className={cn(
                        "py-2 pr-3 text-right num font-bold",
                        isGain
                          ? "text-[var(--color-success)]"
                          : "text-[var(--color-danger)]",
                      )}
                    >
                      {isGain ? "+" : ""}
                      {gain.toFixed(2)}
                    </td>
                    <td className="py-2 pr-3 text-right num text-[var(--color-text-muted)]">
                      {d.holding_period_days}
                    </td>
                    <td className="py-2 pr-3">
                      <span
                        className={cn(
                          "text-[10px] px-1.5 py-0.5 rounded font-semibold",
                          d.income_type === "staking"
                            ? "bg-[var(--color-accent)]/15 text-[var(--color-accent)]"
                            : d.income_type === "airdrop"
                              ? "bg-[var(--color-warning)]/15 text-[var(--color-warning)]"
                              : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]",
                        )}
                      >
                        {d.income_type}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>
      )}

      {/* Empty state */}
      {!report && !loading && (
        <div className="panel p-8 text-center">
          <Receipt size={32} className="mx-auto text-[var(--color-text-muted)] mb-3" />
          <p className="text-[14px] text-[var(--color-text-muted)]">
            Select your country, year, and lot-relief method, then click Calculate to generate your tax report.
          </p>
        </div>
      )}

      {/* Saved reports */}
      {savedReports.length > 0 && (
        <Panel
          title="Saved Reports"
          icon={<Save size={16} />}
          tone="primary"
        >
          <div className="space-y-2">
            {savedReports.map((r) => (
              <div
                key={r.id}
                className="flex items-center justify-between gap-3 bg-[var(--color-surface-2)] rounded-lg px-3 py-2.5"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-[18px]">
                    {countryFlag(r.country)}
                  </span>
                  <div className="min-w-0">
                    <div className="text-[13px] font-bold text-[var(--color-text)]">
                      {r.country_name || r.country} — {r.year}
                    </div>
                    <div className="text-[11px] text-[var(--color-text-muted)]">
                      Method: {r.method.toUpperCase()} ·{" "}
                      {r.created_at ? new Date(r.created_at).toLocaleDateString() : "—"}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleExportCsv(r.id)}
                  >
                    <Download size={12} />
                    CSV
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function countryFlag(code: string): string {
  const flags: Record<string, string> = {
    ES: "🇪🇸", US: "🇺🇸", UK: "🇬🇧", DE: "🇩🇪",
    AU: "🇦🇺", CA: "🇨🇦", FR: "🇫🇷", JP: "🇯🇵",
  };
  return flags[code] || "🏳️";
}

function downloadCsvString(csv: string, filename: string) {
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function generateCsvFromReport(report: TaxReport): string {
  const rows: string[] = [];
  rows.push("Symbol,Buy Date,Sell Date,Quantity,Buy Price,Sell Price,Buy Fee,Sell Fee,Proceeds,Cost Basis,Gain/Loss,Holding Period (days),Income Type");

  for (const d of report.disposals) {
    rows.push([
      d.symbol,
      (d.buy_timestamp || "").slice(0, 10),
      (d.sell_timestamp || "").slice(0, 10),
      d.quantity,
      d.buy_price,
      d.sell_price,
      d.buy_fee,
      d.sell_fee,
      d.proceeds,
      d.cost_basis,
      d.gain,
      d.holding_period_days,
      d.income_type,
    ].join(","));
  }

  rows.push("");
  rows.push("SUMMARY");
  rows.push(`Country,${report.country}`);
  rows.push(`Year,${report.year}`);
  rows.push(`Method,${report.method}`);
  rows.push(`Currency,${report.currency}`);
  rows.push(`Total Proceeds,${report.summary.total_proceeds}`);
  rows.push(`Total Cost Basis,${report.summary.total_cost_basis}`);
  rows.push(`Total Gains,${report.summary.total_gains}`);
  rows.push(`Total Losses,${report.summary.total_losses}`);
  rows.push(`Net Gain,${report.summary.net_gain}`);
  rows.push(`Taxable Gain,${report.summary.taxable_gain}`);
  rows.push(`Estimated Tax,${report.summary.estimated_tax}`);

  return rows.join("\n");
}
