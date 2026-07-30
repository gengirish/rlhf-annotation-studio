import { SignIn } from "@clerk/nextjs";

export const metadata = { title: "Sign in — RLHF Annotation Studio" };

export default function SignInPage() {
  return (
    <main
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        padding: 24
      }}
    >
      <SignIn />
    </main>
  );
}
