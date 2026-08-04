import {useState} from "react";
import {chat} from "./api";

function App(){

const [msg,setMsg]=useState("");
const [reply,setReply]=useState("");

async function send(){

 const result=await chat({

  provider:"ollama",

  model:"qwen3:4b",

  tools_enabled:true,

  messages:[
    {
      role:"user",
      content:msg
    }
  ]

 });

 setReply(result.content);

}


return (

<div style={{
padding:40,
fontFamily:"Arial"
}}>

<h1>
Linlin Agent
</h1>


<textarea

value={msg}

onChange={
e=>setMsg(e.target.value)
}

rows={5}

cols={50}

/>


<br/>


<button onClick={send}>
送出
</button>


<h2>
AI Response
</h2>


<pre>
{reply}
</pre>


</div>

)

}


export default App;