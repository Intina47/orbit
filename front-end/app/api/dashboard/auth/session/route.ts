import { NextRequest, NextResponse } from "next/server"

import {
  buildDashboardSessionStatus,
  dashboardLoginConfigError,
} from "@/lib/dashboard-auth"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store",
}

export async function GET(request: NextRequest) {
  const configError = dashboardLoginConfigError()
  if (configError) {
    return NextResponse.json({ detail: configError }, { status: 500, headers: NO_STORE_HEADERS })
  }

  return NextResponse.json(buildDashboardSessionStatus(request), {
    status: 200,
    headers: NO_STORE_HEADERS,
  })
}
