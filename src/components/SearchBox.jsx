import { useState } from "react";

function SearchBox({ onSearch }) {
    const [question, setQuestion] = useState("");

    return (
        <div>
            <input
                type="text"
                placeholder="Nhập câu hỏi về loài chim..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                style={{ width: "300px" }}
            />
            <button onClick={() => onSearch(question)}>
                Tra cứu
            </button>
        </div>
    );
}

export default SearchBox;
