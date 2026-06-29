"use server";

import { cookies } from "next/headers";

export async function sendChatAction(text: string, image: string | null = null) {
    try {
        const cookieStore = await cookies();
        const cookieHeader = cookieStore.toString();

        const res = await fetch("http://127.0.0.1:8000/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(cookieHeader ? { Cookie: cookieHeader } : {}),
            },
            body: JSON.stringify({ message: text, image: image }),
        });

        const status = res.status;
        const data = await res.json();

        return {
            status,
            ok: res.ok,
            data,
        };
    } catch (err: any) {
        return {
            status: 500,
            ok: false,
            error: err.message || "Failed to communicate with AI server",
        };
    }
}