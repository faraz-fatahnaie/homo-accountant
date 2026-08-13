import { GeneralLedgerClient } from "./_client";

export default async function GeneralLedgerPage({
  searchParams,
}: {
  searchParams: Promise<{ account_code?: string }>;
}) {
  const { account_code } = await searchParams;
  return <GeneralLedgerClient initialAccountCode={account_code ?? ""} />;
}
