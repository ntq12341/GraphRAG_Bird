import { useState } from "react";
import "./App.css";

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim()) return;

    // Add user message
    const userMsg = { role: "user", content: input };

    // Mock bot reply
    const botMsg = {
      role: "assistant",
      content: "Chim Chào mào thường sống ở rừng thưa, công viên và khu dân cư."
    };

    setMessages(prev => [...prev, userMsg, botMsg]);
    setInput("");
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        GraphRAG Bird Assistant 🐦
      </div>

      <div className="chat-messages">
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            {m.content}
          </div>
        ))}
      </div>

      <div className="chat-input">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Nhập câu hỏi về loài chim..."
          onKeyDown={e => e.key === "Enter" && handleSend()}
        />
        <button onClick={handleSend}>Gửi</button>
      </div>
    </div>
  );
}

export default App;
