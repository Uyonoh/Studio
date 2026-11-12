"use client";

import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  CreditCard,
  Gift,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  RotateCcw,
  Zap,
} from "lucide-react";
import { useCreditBalance } from "@/hooks/use-credits";
import {
  useCreditTransactions,
  type CreditTransaction,
} from "@/hooks/use-credit-transactions";
import { formatCredits, formatDateTime, formatDelta, shortId } from "./format";

interface UsagePanelProps {
  workspaceId?: string | null;
}

function reasonMeta(reason: string) {
  switch (reason) {
    case "refund":
      return {
        label: "Refund",
        icon: RotateCcw,
        iconClass: "text-emerald-400",
        chipClass: "bg-emerald-500/10 border-emerald-500/25",
      };
    case "grant":
      return {
        label: "Credit grant",
        icon: Gift,
        iconClass: "text-[#A995FF]",
        chipClass: "bg-[#7C5CFF]/10 border-[#7C5CFF]/25",
      };
    case "purchase":
      return {
        label: "Credit purchase",
        icon: CreditCard,
        iconClass: "text-[#A995FF]",
        chipClass: "bg-[#7C5CFF]/10 border-[#7C5CFF]/25",
      };
    default:
      return {
        label: "Generation",
        icon: ImageIcon,
        iconClass: "text-[#9AA1B2]",
        chipClass: "bg-[#1B1E26] border-[#262A35]",
      };
  }
}

function TransactionRow({ transaction }: { transaction: CreditTransaction }) {
  const meta = reasonMeta(transaction.reason);
  const Icon = meta.icon;
  const delta = Number(transaction.delta);
  const isSpend = delta < 0;

  return (
    <li className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:gap-4">
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${meta.chipClass}`}
      >
        <Icon className={`h-4 w-4 ${meta.iconClass}`} />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-sm font-medium text-[#E8EAF0]">{meta.label}</span>
          {transaction.model_name && (
            <span className="text-xs text-[#9AA1B2]">· {transaction.model_name}</span>
          )}
          {isSpend ? (
            <ArrowDownRight className="h-3.5 w-3.5 text-[#F87171]" aria-hidden="true" />
          ) : (
            <ArrowUpRight className="h-3.5 w-3.5 text-emerald-400" aria-hidden="true" />
          )}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-[#9AA1B2]">
          <span className="font-mono">{formatDateTime(transaction.created_at)}</span>
          {transaction.job_id && (
            <>
              <span aria-hidden="true">·</span>
              <span className="font-mono">job {shortId(transaction.job_id)}</span>
            </>
          )}
          {transaction.prompt && (
            <>
              <span aria-hidden="true">·</span>
              <span className="max-w-[28rem] truncate">{transaction.prompt}</span>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between gap-4 sm:flex-col sm:items-end sm:justify-center sm:gap-0.5">
        <span
          className={`text-sm font-semibold font-mono ${
            isSpend ? "text-[#F87171]" : "text-emerald-400"
          }`}
        >
          {formatDelta(transaction.delta)}
        </span>
        <span className="text-[11px] font-mono text-[#9AA1B2]">
          balance {formatCredits(transaction.balance_after)}
        </span>
      </div>
    </li>
  );
}

function SummaryCard({
  label,
  value,
  detail,
  accent,
}: {
  label: string;
  value: string;
  detail: string;
  accent?: "primary";
}) {
  return (
    <div className="rounded-2xl border border-[#262A35] bg-[#14161C] p-5">
      <div className="text-[10px] font-mono uppercase tracking-wider text-[#9AA1B2]">
        {label}
      </div>
      <div
        className={`mt-2 text-2xl font-bold tracking-tight ${
          accent === "primary" ? "text-[#A995FF]" : "text-[#E8EAF0]"
        }`}
      >
        {value}
      </div>
      <p className="mt-1 text-xs text-[#9AA1B2]">{detail}</p>
    </div>
  );
}

export function UsagePanel({ workspaceId }: UsagePanelProps) {
  const balanceQuery = useCreditBalance(workspaceId);
  const transactionsQuery = useCreditTransactions(workspaceId);

  const summary = transactionsQuery.data?.pages[0]?.summary;
  const transactions = transactionsQuery.data?.pages.flatMap((page) => page.items) ?? [];
  const windowDays = summary?.window_days ?? 30;

  const handleRefresh = () => {
    balanceQuery.refetch();
    transactionsQuery.refetch();
  };

  return (
    <div className="space-y-6">
      {/* Balance + activity headlines */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="relative overflow-hidden rounded-2xl border border-[#262A35] bg-[#14161C] p-5">
          <div className="pointer-events-none absolute -right-6 -top-6 h-32 w-32 rounded-full bg-[#7C5CFF]/10 blur-2xl" />
          <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-[#9AA1B2]">
            <span>Available balance</span>
            <button
              type="button"
              onClick={handleRefresh}
              aria-label="Refresh credit activity"
              className="rounded-lg p-1 text-[#9AA1B2] transition-colors hover:bg-[#1B1E26] hover:text-[#E8EAF0]"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${
                  balanceQuery.isFetching || transactionsQuery.isFetching ? "animate-spin" : ""
                }`}
              />
            </button>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span
              data-testid="usage-balance"
              className="text-3xl font-bold tracking-tight text-[#E8EAF0]"
            >
              {balanceQuery.isLoading ? "—" : formatCredits(balanceQuery.data)}
            </span>
            <span className="text-sm text-[#9AA1B2]">credits</span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-[#9AA1B2]">
            Credits are reserved per generation and refunded automatically when a job fails or is
            canceled.
          </p>
        </div>

        <SummaryCard
          label={`Spent · last ${windowDays} days`}
          value={`${formatCredits(summary?.spent)}`}
          detail={`${formatCredits(summary?.granted)} credits granted · ${formatCredits(
            summary?.refunded
          )} refunded`}
        />

        <SummaryCard
          label={`Activity · last ${windowDays} days`}
          value={`${summary?.transactions ?? 0}`}
          detail="Ledger entries across generations, refunds, and grants."
          accent="primary"
        />
      </div>

      {/* Ledger */}
      <div className="overflow-hidden rounded-2xl border border-[#262A35] bg-[#14161C]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#262A35] px-5 py-4">
          <div>
            <h3 className="flex items-center gap-2 text-base font-semibold text-[#E8EAF0]">
              <Zap className="h-4 w-4 text-[#A995FF]" />
              Credit activity
            </h3>
            <p className="mt-0.5 text-xs text-[#9AA1B2]">
              Every balance change is recorded in the append-only ledger.
            </p>
          </div>
          <span className="rounded-full border border-[#262A35] bg-[#1B1E26] px-2.5 py-1 text-[12px] font-mono text-[#A995FF]">
            {formatCredits(balanceQuery.data)} available
          </span>
        </div>

        {transactionsQuery.isLoading ? (
          <div className="flex items-center justify-center gap-2 px-5 py-12 text-sm text-[#9AA1B2]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading credit activity…
          </div>
        ) : transactionsQuery.isError ? (
          <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
            <AlertCircle className="h-6 w-6 text-[#F87171]" />
            <p className="text-sm text-[#E8EAF0]">
              {transactionsQuery.error instanceof Error
                ? transactionsQuery.error.message
                : "Could not load credit activity."}
            </p>
            <button
              type="button"
              onClick={() => transactionsQuery.refetch()}
              className="rounded-lg border border-[#262A35] bg-[#1B1E26] px-3 py-1.5 text-xs font-medium text-[#A995FF] transition-colors hover:text-[#E8EAF0]"
            >
              Try again
            </button>
          </div>
        ) : transactions.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-5 py-12 text-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#262A35] bg-[#1B1E26]">
              <Zap className="h-5 w-5 text-[#A995FF]" />
            </div>
            <p className="text-sm font-medium text-[#E8EAF0]">No credit activity yet</p>
            <p className="max-w-sm text-xs text-[#9AA1B2]">
              Submit a generation and its credit reservation will appear here, along with any
              refunds or grants.
            </p>
          </div>
        ) : (
          <>
            <ul className="divide-y divide-[#262A35]">
              {transactions.map((transaction) => (
                <TransactionRow key={transaction.id} transaction={transaction} />
              ))}
            </ul>
            <div className="flex items-center justify-between gap-3 border-t border-[#262A35] px-4 py-3">
              <span className="text-xs text-[#9AA1B2]">
                {transactions.length} transaction{transactions.length === 1 ? "" : "s"} loaded
              </span>
              {transactionsQuery.hasNextPage && (
                <button
                  type="button"
                  onClick={() => transactionsQuery.fetchNextPage()}
                  disabled={transactionsQuery.isFetchingNextPage}
                  className="flex items-center gap-1.5 rounded-lg border border-[#262A35] bg-[#1B1E26] px-3 py-1.5 text-xs font-medium text-[#A995FF] transition-colors hover:text-[#E8EAF0] disabled:opacity-60"
                >
                  {transactionsQuery.isFetchingNextPage && (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  )}
                  Load older activity
                </button>
              )}
            </div>
          </>
        )}
      </div>

      <p className="text-xs text-[#9AA1B2]">
        Need more credits? Credit purchases and workspace billing are handled by your account
        administrator.
      </p>
    </div>
  );
}
