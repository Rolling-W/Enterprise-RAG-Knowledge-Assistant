export default function App() {
    return (
        <main style={{
            fontFamily: 'Arial, sans-serif',
            maxWidth: '960px',
            margin: '80px auto',
            padding: '24px',
            background: '#f4f7fb',
            borderRadius: '16px',
            boxShadow: '0 8px 30px rgba(15, 23, 42, 0.08)'
        }}>
            <h1 style={{ color: '#0f172a', marginBottom: '12px' }}>Enterprise RAG Knowledge Assistant</h1>
            <p style={{ color: '#475569', fontSize: '18px' }}>
                A demo interface for secure enterprise document search and synthesis.
            </p>

            <div style={{ marginTop: '28px', display: 'grid', gap: '16px' }}>
                <div style={{ background: '#ffffff', padding: '20px', borderRadius: '12px' }}>
                    <strong style={{ color: '#0f172a' }}>Query</strong>
                    <p style={{ color: '#334155', marginTop: '8px' }}>employee benefits policy</p>
                </div>

                <div style={{ background: '#ffffff', padding: '20px', borderRadius: '12px' }}>
                    <strong style={{ color: '#0f172a' }}>Role</strong>
                    <p style={{ color: '#334155', marginTop: '8px' }}>Manager</p>
                </div>

                <div style={{ background: '#ffffff', padding: '20px', borderRadius: '12px' }}>
                    <strong style={{ color: '#0f172a' }}>Result</strong>
                    <p style={{ color: '#334155', marginTop: '8px' }}>
                        Employee_Handbook.pdf — page 12, line 45
                    </p>
                </div>
            </div>
        </main>
    );
}
