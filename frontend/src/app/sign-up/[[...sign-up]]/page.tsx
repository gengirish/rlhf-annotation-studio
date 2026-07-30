import { SignUp } from "@clerk/nextjs";

export const metadata = { title: "Sign up — RLHF Annotation Studio" };

export default function SignUpPage() {
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
      <SignUp />
    </main>
  );
}
