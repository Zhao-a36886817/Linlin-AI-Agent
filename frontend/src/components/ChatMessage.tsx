import type { ChatMessage as ChatMessageType } from "../types";

interface Props {
    message: ChatMessageType;
}


export default function ChatMessage({
    message
}: Props) {

    return (
        <div className={`message ${message.role}`}>

            <div className="role">
                {message.role}
            </div>

            <div className="content">
                {message.content}
            </div>

        </div>
    );
}