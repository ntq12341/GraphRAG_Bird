function ResultPanel({ result }) {
    if (!result) return null;

    return (
        <div style={{ marginTop: "20px" }}>
            <h3>Kết quả</h3>
            <p><b>Trả lời:</b> {result.answer}</p>

            <p><b>Thực thể liên quan:</b></p>
            <ul>
                {result.entities.map((e, i) => (
                    <li key={i}>{e}</li>
                ))}
            </ul>
        </div>
    );
}

export default ResultPanel;
