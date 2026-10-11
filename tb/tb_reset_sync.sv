`timescale 1ns/1ps

module tb_reset_sync;

    logic clk_a;
    logic clk_b;
    logic rst_n_async;

    logic rst_a_n;
    logic rst_b_n;

    reset_sync u_reset_sync_a (
        .clk (clk_a),
        .rst_n_async (rst_n_async),
        .rst_n_sync (rst_a_n)
    );

    reset_sync u_reset_sync_b (
        .clk (clk_b),
        .rst_n_async (rst_n_async),
        .rst_n_sync (rst_b_n)
    );

    initial clk_a = 1'b0;
    always #5 clk_a = ~clk_a;

    initial clk_b = 1'b0;
    always #7 clk_b = ~clk_b;

    initial begin
        $dumpfile("results/reset_sync.vcd");
        $dumpvars(0, tb_reset_sync);

        rst_n_async = 1'b0;
        #1;

        if (rst_a_n !== 1'b0 || rst_b_n !== 1'b0)
            $fatal(
                1,
                "INITIAL RESET FAILED: rst_a_n=%b rst_b_n=%b",
                rst_a_n,
                rst_b_n
            );
        else
            $display("INITIAL RESET PASS");

        #2;
        rst_n_async = 1'b1;

        fork
            begin
                @(posedge clk_a);
                #1;

                if (rst_a_n !== 1'b0)
                    $fatal(
                        1,
                        "DOMAIN A RELEASED TOO EARLY: rst_a_n=%b",
                        rst_a_n
                    );

                @(posedge clk_a);
                #1;

                if (rst_a_n !== 1'b1)
                    $fatal(
                        1,
                        "DOMAIN A RELEASE FAILED: rst_a_n=%b",
                        rst_a_n
                    );
                
                $display("DOMAIN A RELEASE PASS");
            end

            begin
                @(posedge clk_b);
                #1;

                if (rst_b_n !== 1'b0)
                    $fatal(
                        1,
                        "DOMAIN B RELEASED TOO EARLY: rst_b_n=%b",
                        rst_b_n
                    );
                
                @(posedge clk_b);
                #1;

                if (rst_b_n !== 1'b1)
                    $fatal(
                        1,
                        "DOMAIN B RELEASE FAILED: rst_b_n=%b",
                        rst_b_n
                    );
                
                $display("DOMAIN B RELEASE PASS");
            end
        join

        #2;
        rst_n_async = 1'b0;
        #0.5;

        if (rst_a_n !== 1'b0 || rst_b_n !== 1'b0)
            $fatal(
                1,
                "ASYNC ASSERT FAILED: rst_a_n=%b rst_b_n=%b",
                rst_a_n,
                rst_b_n
            );
        else
            $display("ASYNC ASSERT PASS");
        
        $display("RESET SYNC ALL PASS");
        $finish;
    end 

endmodule