export default function App() {
  return <p>Calgary water main breaks dashboard</p>;
}

// test-code: 
/*
import { useEffect } from "react";
import { fetchAnnualWatermainSummary, fetchWatermainBreakSummary } from "./api/apiEndpoints";

export default function App() {
  useEffect(() => {
    fetchWatermainBreakSummary().then(console.log).catch(console.error);
    fetchAnnualWatermainSummary(2020, 2020).then(console.log).catch(console.error);
  }, []);

  return <p>Open the browser console.</p>;
}
/* */