import {
    useState
} from "react";

import {
    chat
} from "../api";

import type {
    ChatMessage
} from "../types";

import ChatMessageView from "./ChatMessage";


export default function ChatBox() {


    const [messages, setMessages] =
        useState<ChatMessage[]>([]);


    const [input,setInput] =
        useState("");


    const [loading,setLoading] =
        useState(false);



    async function send(){


        if(!input.trim()) return;


        const userMessage:ChatMessage =
        {
            role:"user",
            content:input
        };


        const newMessages=[
            ...messages,
            userMessage
        ];


        setMessages(newMessages);
        setInput("");
        setLoading(true);



        try {


            const result =
            await chat({

                provider:"ollama",

                model:"qwen3:4b",

                tools_enabled:true,

                messages:newMessages

            });



            setMessages(prev=>[

                ...prev,

                {
                    role:"assistant",
                    content:result.content
                }

            ]);



        }
        catch(error){

            setMessages(prev=>[

                ...prev,

                {
                    role:"assistant",
                    content:
                    String(error)
                }

            ]);

        }
        finally{

            setLoading(false);

        }

    }



    return (

        <div className="chatbox">


            <div className="messages">

                {
                    messages.map(
                        (m,index)=>(

                        <ChatMessageView
                            key={index}
                            message={m}
                        />

                    ))
                }


                {
                    loading &&
                    <div>
                        Linlin 思考中...
                    </div>
                }


            </div>



            <div className="input-area">


                <input

                    value={input}

                    onChange={
                        e=>setInput(e.target.value)
                    }

                    onKeyDown={
                        e=>{
                            if(e.key==="Enter")
                                send();
                        }
                    }

                    placeholder="輸入訊息..."

                />


                <button
                    onClick={send}
                >
                    送出
                </button>


            </div>


        </div>

    );

}